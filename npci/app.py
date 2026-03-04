import logging
import os
import sys
import requests
from datetime import datetime, timezone
from flask import Flask, jsonify, request, Response
from lxml import etree

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [npci] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)

# Set Flask's werkzeug logger to INFO to see all HTTP requests
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)

app = Flask(__name__)


# Request logging middleware
@app.before_request
def log_request():
    logger.info("==> Incoming %s %s | Content-Type: %s | Content-Length: %s | Remote: %s",
                request.method, request.path,
                request.content_type or "N/A",
                request.content_length or 0,
                request.remote_addr)
    if request.args:
        logger.info("    Query params: %s", dict(request.args))
    if request.is_json:
        logger.info("    JSON body: %s", request.get_json())


@app.after_request
def log_response(response):
    logger.info("<== Response %s %s | Status: %s | Content-Type: %s | Content-Length: %s",
                request.method, request.path,
                response.status_code,
                response.content_type or "N/A",
                response.content_length or 0)
    return response

NS = "http://npci.org/upi/schema/"
PAYEE_PSP_URL = os.environ.get("PAYEE_PSP_URL", "http://payee_psp:5000")
REM_BANK_URL = os.environ.get("REM_BANK_URL", "http://rem_bank:5000")
BENE_BANK_URL = os.environ.get("BENE_BANK_URL", "http://bene_bank:5000")
PAYER_PSP_URL = os.environ.get("PAYER_PSP_URL", "http://payer_psp:5000")

# Keyed by reqMsgId (from ReqPay we sent to rem_bank). Used when RespPay DEBIT arrives to build ReqPay CREDIT for bene_bank.
_pending_debits: dict[str, dict] = {}


def _xsd_path(filename: str) -> str:
    base = os.path.dirname(os.path.abspath(__file__))
    for rel in (f"schemas/{filename}", f"../common/schemas/{filename}"):
        p = os.path.normpath(os.path.join(base, rel))
        if os.path.isfile(p):
            return p
    return os.path.join(base, "schemas", filename)


def _validate_reqvaladd(xml_bytes: bytes) -> None:
    """Validate XML against common/schemas/upi_req_valadd.xsd. Raises ValueError on invalid."""
    path = _xsd_path("upi_req_valadd.xsd")
    if not os.path.isfile(path):
        raise ValueError("ReqValAdd XSD not found")
    with open(path, "rb") as f:
        schema_doc = etree.parse(f)
    schema = etree.XMLSchema(schema_doc)
    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML: {e}") from e
    if not schema.validate(doc):
        raise ValueError("ReqValAdd does not match schema: " + str(schema.error_log))


def _validate_respvaladd(xml_bytes: bytes) -> None:
    """Validate XML against common/schemas/upi_resp_valadd.xsd. Raises ValueError on invalid."""
    path = _xsd_path("upi_resp_valadd.xsd")
    if not os.path.isfile(path):
        raise ValueError("RespValAdd XSD not found")
    with open(path, "rb") as f:
        schema_doc = etree.parse(f)
    schema = etree.XMLSchema(schema_doc)
    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML: {e}") from e
    if not schema.validate(doc):
        raise ValueError("RespValAdd does not match schema: " + str(schema.error_log))


def _validate_reqpay(xml_bytes: bytes) -> None:
    """Validate XML against common/schemas/upi_pay_request.xsd. Raises ValueError on invalid."""
    path = _xsd_path("upi_pay_request.xsd")
    if not os.path.isfile(path):
        raise ValueError("ReqPay XSD not found")
    with open(path, "rb") as f:
        schema_doc = etree.parse(f)
    schema = etree.XMLSchema(schema_doc)
    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML: {e}") from e
    if not schema.validate(doc):
        raise ValueError("ReqPay does not match schema: " + str(schema.error_log))


def _validate_resppay(xml_bytes: bytes) -> None:
    """Validate XML against common/schemas/upi_resppay_response.xsd. Raises ValueError on invalid."""
    path = _xsd_path("upi_resppay_response.xsd")
    if not os.path.isfile(path):
        raise ValueError("RespPay XSD not found")
    with open(path, "rb") as f:
        schema_doc = etree.parse(f)
    schema = etree.XMLSchema(schema_doc)
    try:
        doc = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as e:
        raise ValueError(f"Invalid XML: {e}") from e
    if not schema.validate(doc):
        raise ValueError("RespPay does not match schema: " + str(schema.error_log))


def _q(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _build_reqpay_debit(reqvaladd_bytes: bytes) -> bytes | None:
    """
    Build ReqPay with Txn.type=DEBIT from ReqValAdd for remitter bank (debit payer's account).
    Returns None if ReqValAdd has no Payer with addr. ReqValAdd has no amount; uses placeholder 1.00 INR.
    Preserves original Payer and Payee attributes including code, type, seqNum.
    """
    try:
        root = etree.fromstring(reqvaladd_bytes)
    except etree.XMLSyntaxError:
        return None
    head = root.find(f".//{_q('Head')}")
    txn = root.find(f".//{_q('Txn')}")
    payer = root.find(f".//{_q('Payer')}")
    payee = root.find(f".//{_q('Payee')}")
    if head is None or txn is None or payee is None:
        return None
    payer_addr = (payer.get("addr") or "").strip() if payer is not None else ""
    if not payer_addr:
        return None
    payee_addr = (payee.get("addr") or "").strip()
    if not payee_addr:
        return None

    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req_msg = head.get("msgId") or "valadd"
    txn_id = txn.get("id") or "valadd-txn"

    req = etree.Element(_q("ReqPay"))
    h = etree.SubElement(req, _q("Head"))
    h.set("ver", head.get("ver") or "2.0")
    h.set("ts", ts)
    h.set("orgId", "NPCI")
    h.set("msgId", f"debit-{req_msg}")
    h.set("prodType", head.get("prodType") or "UPI")

    t = etree.SubElement(req, _q("Txn"))
    t.set("id", txn_id)
    t.set("type", "DEBIT")
    if txn.get("purpose"):
        t.set("purpose", txn.get("purpose"))

    p = etree.SubElement(req, _q("Payer"))
    p.set("addr", payer_addr)
    # Preserve original Payer attributes
    if payer is not None:
        if payer.get("name"):
            p.set("name", payer.get("name"))
        if payer.get("seqNum"):
            p.set("seqNum", payer.get("seqNum"))
        if payer.get("type"):
            p.set("type", payer.get("type"))
        if payer.get("code"):
            p.set("code", payer.get("code"))
    amt = etree.SubElement(p, _q("Amount"))
    amt.set("value", "1.00")
    amt.set("curr", "INR")

    payees = etree.SubElement(req, _q("Payees"))
    pe = etree.SubElement(payees, _q("Payee"))
    pe.set("addr", payee_addr)
    # Preserve original Payee attributes
    if payee.get("name"):
        pe.set("name", payee.get("name"))
    if payee.get("seqNum"):
        pe.set("seqNum", payee.get("seqNum"))
    if payee.get("type"):
        pe.set("type", payee.get("type"))
    if payee.get("code"):
        pe.set("code", payee.get("code"))

    return etree.tostring(req, encoding="UTF-8", xml_declaration=True)


def _reqpay_as_debit(reqpay_bytes: bytes) -> bytes | None:
    """
    Return ReqPay XML with Txn.type=DEBIT so remitter bank debits the payer.
    If parse fails or Txn missing, returns None.
    Preserves all original attributes including Payer.code and Payee.code.
    """
    try:
        root = etree.fromstring(reqpay_bytes)
    except etree.XMLSyntaxError:
        return None
    txn = root.find(f".//{_q('Txn')}")
    if txn is None:
        return None
    
    # Log original attributes for debugging
    payer = root.find(f".//{_q('Payer')}")
    payees = root.find(f".//{_q('Payees')}")
    payee = payees.find(_q("Payee")) if payees is not None else None
    logger.info("[NPCI] _reqpay_as_debit - Original Payer.code=%s, Payee.code=%s",
                payer.get("code") if payer is not None else None,
                payee.get("code") if payee is not None else None)
    
    # Only modify Txn.type - preserve everything else
    txn.set("type", "DEBIT")
    
    result = etree.tostring(root, encoding="UTF-8", xml_declaration=True)
    
    # Verify attributes are preserved after serialization
    try:
        verify_root = etree.fromstring(result)
        verify_payer = verify_root.find(f".//{_q('Payer')}")
        verify_payees = verify_root.find(f".//{_q('Payees')}")
        verify_payee = verify_payees.find(_q("Payee")) if verify_payees is not None else None
        logger.info("[NPCI] _reqpay_as_debit - After serialization Payer.code=%s, Payee.code=%s",
                    verify_payer.get("code") if verify_payer is not None else None,
                    verify_payee.get("code") if verify_payee is not None else None)
    except Exception as e:
        logger.warning("[NPCI] _reqpay_as_debit - Failed to verify serialized XML: %s", e)
    
    return result


def _parse_reqpay_fields(reqpay_bytes: bytes) -> dict | None:
    """Extract msgId, payee_addr, amount, txn_id, payer_addr, ver, prodType, payee_name, payer_code, payee_code from ReqPay. For storing before rem_bank DEBIT."""
    try:
        root = etree.fromstring(reqpay_bytes)
    except etree.XMLSyntaxError:
        return None
    head = root.find(f".//{_q('Head')}")
    txn = root.find(f".//{_q('Txn')}")
    payer = root.find(f".//{_q('Payer')}")
    payees = root.find(f".//{_q('Payees')}")
    payee = payees.find(_q("Payee")) if payees is not None else None
    
    # Debug: log all Payee attributes to see what we're getting
    if payees is not None:
        logger.info("[NPCI] _parse_reqpay_fields - Payees element found, tag=%s, children=%s", 
                    payees.tag, [child.tag for child in payees])
        # Try to find Payee using different methods
        payee_direct = payees.find(_q("Payee"))
        payee_iter = None
        for child in payees:
            if child.tag == _q("Payee") or child.tag.endswith("}Payee"):
                payee_iter = child
                break
        logger.info("[NPCI] _parse_reqpay_fields - payee via find()=%s, payee via iteration=%s", 
                    payee_direct, payee_iter)
        # Use the one that worked
        if payee is None and payee_iter is not None:
            payee = payee_iter
            logger.info("[NPCI] _parse_reqpay_fields - Using payee from iteration")
    
    if payee is not None:
        logger.info("[NPCI] _parse_reqpay_fields - Payee element found, tag=%s, all attributes: %s", 
                    payee.tag, dict(payee.attrib))
    else:
        logger.warning("[NPCI] _parse_reqpay_fields - Payee element NOT found! payees=%s", payees)
    
    if head is None or txn is None or payer is None or payee is None:
        return None
    msg_id = (head.get("msgId") or "").strip()
    if not msg_id:
        return None
    amt_el = payer.find(_q("Amount"))
    amount = float(amt_el.get("value") or 0) if amt_el is not None else 0.0
    
    # Extract values with detailed logging
    payer_code = (payer.get("code") or "").strip() or None
    payee_code = (payee.get("code") or "").strip() or None
    
    logger.info("[NPCI] _parse_reqpay_fields - Extracted: payer_code='%s', payee_code='%s'", payer_code, payee_code)
    
    # Txn.purpose is optional in upi_pay_request.xsd; preserve for DEBIT/CREDIT
    purpose = (txn.get("purpose") or "").strip() or None
    return {
        "msgId": msg_id,
        "payee_addr": (payee.get("addr") or "").strip(),
        "amount": amount,
        "txn_id": (txn.get("id") or "").strip(),
        "payer_addr": (payer.get("addr") or "").strip(),
        "ver": (head.get("ver") or "2.0").strip(),
        "prodType": (head.get("prodType") or "UPI").strip(),
        "payee_name": (payee.get("name") or "").strip() or None,
        "payer_code": payer_code,
        "payee_code": payee_code,
        "payer_name": (payer.get("name") or "").strip() or None,
        "payer_type": (payer.get("type") or "").strip() or None,
        "payer_seqNum": (payer.get("seqNum") or "").strip() or None,
        "payee_type": (payee.get("type") or "").strip() or None,
        "payee_seqNum": (payee.get("seqNum") or "").strip() or None,
        "purpose": purpose,
    }


def _reqvaladd_to_credit_info(reqvaladd_bytes: bytes) -> dict | None:
    """From ReqValAdd build same-shaped info for ReqPay CREDIT. msgId will be 'debit-{head.msgId}' (what rem_bank echoes in RespPay.reqMsgId).
    Preserves original Payer and Payee attributes including code, type, seqNum."""
    try:
        root = etree.fromstring(reqvaladd_bytes)
    except etree.XMLSyntaxError:
        return None
    head = root.find(f".//{_q('Head')}")
    txn = root.find(f".//{_q('Txn')}")
    payer = root.find(f".//{_q('Payer')}")
    payee = root.find(f".//{_q('Payee')}")
    if head is None or txn is None or payee is None:
        return None
    req_msg = (head.get("msgId") or "valadd").strip()
    msg_id = f"debit-{req_msg}"
    purpose = (txn.get("purpose") or "").strip() or None
    return {
        "msgId": msg_id,
        "payee_addr": (payee.get("addr") or "").strip(),
        "amount": 1.0,
        "txn_id": (txn.get("id") or "valadd-txn").strip(),
        "payer_addr": (payer.get("addr") or "").strip() if payer is not None else "",
        "ver": (head.get("ver") or "2.0").strip(),
        "prodType": (head.get("prodType") or "UPI").strip(),
        "payee_name": (payee.get("name") or "").strip() or None,
        "payer_code": (payer.get("code") or "").strip() or None if payer is not None else None,
        "payee_code": (payee.get("code") or "").strip() or None,
        "payer_name": (payer.get("name") or "").strip() or None if payer is not None else None,
        "payer_type": (payer.get("type") or "").strip() or None if payer is not None else None,
        "payer_seqNum": (payer.get("seqNum") or "").strip() or None if payer is not None else None,
        "payee_type": (payee.get("type") or "").strip() or None,
        "payee_seqNum": (payee.get("seqNum") or "").strip() or None,
        "purpose": purpose,
    }


def _parse_resppay(xml_bytes: bytes) -> dict | None:
    """Extract reqMsgId, result, errCode, txnType, txnId from RespPay (DEBIT from rem_bank, CREDIT from bene_bank)."""
    try:
        root = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError:
        return None
    resp = root.find(f".//{_q('Resp')}")
    txn = root.find(f".//{_q('Txn')}")
    if resp is None:
        return None
    return {
        "reqMsgId": (resp.get("reqMsgId") or "").strip() or None,
        "result": (resp.get("result") or "").strip() or None,
        "errCode": (resp.get("errCode") or "").strip() or None,
        "txnType": (txn.get("type") or "").strip() if txn is not None else None,
        "txnId": (txn.get("id") or "").strip() if txn is not None else None,
    }


def _build_reqpay_credit(info: dict) -> bytes:
    """Build ReqPay with Txn.type=CREDIT for beneficiary bank. 
    Preserves original attributes: msgId, payee_addr, amount, txn_id, payer_addr, ver, prodType, payee_name, payer_code, payee_code, etc."""
    # Log the info dict to see what values we're working with
    logger.info("[NPCI] _build_reqpay_credit - Building CREDIT request with info: payer_code=%s, payee_code=%s, payee_name=%s, payee_type=%s",
                info.get("payer_code"), info.get("payee_code"), info.get("payee_name"), info.get("payee_type"))
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req = etree.Element(_q("ReqPay"))
    h = etree.SubElement(req, _q("Head"))
    h.set("ver", info.get("ver") or "2.0")
    h.set("ts", ts)
    h.set("orgId", "NPCI")
    h.set("msgId", f"credit-{info.get('msgId', 'req')}")
    h.set("prodType", info.get("prodType") or "UPI")

    t = etree.SubElement(req, _q("Txn"))
    t.set("id", info.get("txn_id") or "credit-txn")
    t.set("type", "CREDIT")
    if info.get("purpose"):
        t.set("purpose", info["purpose"])

    p = etree.SubElement(req, _q("Payer"))
    p.set("addr", info.get("payer_addr") or "NPCI")
    # Preserve original Payer attributes
    if info.get("payer_name"):
        p.set("name", info["payer_name"])
    if info.get("payer_seqNum"):
        p.set("seqNum", info["payer_seqNum"])
    if info.get("payer_type"):
        p.set("type", info["payer_type"])
    if info.get("payer_code"):
        p.set("code", info["payer_code"])
    
    amt = etree.SubElement(p, _q("Amount"))
    amt.set("value", f"{info.get('amount', 0):.2f}")
    amt.set("curr", "INR")

    payees = etree.SubElement(req, _q("Payees"))
    pe = etree.SubElement(payees, _q("Payee"))
    pe.set("addr", info.get("payee_addr") or "")
    # Preserve original Payee attributes
    if info.get("payee_name"):
        pe.set("name", info["payee_name"])
    if info.get("payee_seqNum"):
        pe.set("seqNum", info["payee_seqNum"])
    if info.get("payee_type"):
        pe.set("type", info["payee_type"])
    if info.get("payee_code"):
        pe.set("code", info["payee_code"])

    return etree.tostring(req, encoding="UTF-8", xml_declaration=True)


def _build_resppay_final(original_req_msg_id: str, txn_id: str, result: str = "SUCCESS", err_code: str | None = None) -> bytes:
    """Build final RespPay for Payer PSP. Per upi_resppay_response.xsd. err_code e.g. INSUFFICIENT_BALANCE when result=FAILURE."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    root = etree.Element(_q("RespPay"))
    h = etree.SubElement(root, _q("Head"))
    h.set("ver", "2.0")
    h.set("ts", ts)
    h.set("orgId", "NPCI")
    h.set("msgId", f"resppay-final-{original_req_msg_id}")
    h.set("prodType", "UPI")
    t = etree.SubElement(root, _q("Txn"))
    t.set("id", txn_id or "final-txn")
    t.set("type", "PAY")
    r = etree.SubElement(root, _q("Resp"))
    r.set("reqMsgId", original_req_msg_id)
    r.set("result", result)
    if err_code:
        r.set("errCode", err_code)
    return etree.tostring(root, encoding="UTF-8", xml_declaration=True)


@app.get("/health")
def health() -> tuple[dict, int]:
    return jsonify(status="ok"), 200


@app.post("/api/reqvaladd")
def reqvaladd() -> tuple[Response | dict, int]:
    """
    ReqValAdd: validate (upi_req_valadd.xsd), route to Payee PSP.
    RespValAdd: receive from Payee PSP, validate (upi_resp_valadd.xsd), route to Payer PSP.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    ct = request.content_type or ""
    if "xml" not in ct and "application/octet-stream" not in ct:
        return jsonify(error="Content-Type must be application/xml or text/xml"), 415
    try:
        _validate_reqvaladd(request.data)
    except ValueError as e:
        return jsonify(error=str(e)), 400
    try:
        r = requests.post(
            f"{PAYEE_PSP_URL.rstrip('/')}/api/reqvaladd",
            data=request.data,
            headers={"Content-Type": "application/xml"},
            timeout=120,
        )
    except requests.RequestException as e:
        return jsonify(error=f"Payee PSP unreachable: {e}"), 502
    # RespValAdd from Payee PSP: validate and route to Payer PSP (return to caller)
    if r.status_code == 200 and r.content and ("xml" in (r.headers.get("Content-Type") or "")):
        try:
            _validate_respvaladd(r.content)
        except ValueError as e:
            return jsonify(error=f"Invalid RespValAdd from Payee PSP: {e}"), 502
        # After RespValAdd: send ReqPay with Txn.type=DEBIT to remitter bank to debit payer's account
        reqpay_bytes = _build_reqpay_debit(request.data)
        if reqpay_bytes:
            # Store so when RespPay DEBIT arrives we can build ReqPay CREDIT for bene_bank (key = debit-{msgId} in built ReqPay)
            info = _reqvaladd_to_credit_info(request.data)
            if info:
                _pending_debits[info["msgId"]] = info
            url = f"{REM_BANK_URL.rstrip('/')}/api/reqpay"
            logger.info("[NPCI] Forwarding ReqPay (DEBIT) to rem_bank [reqvaladd]: %s", url)
            try:
                r = requests.post(url, data=reqpay_bytes, headers={"Content-Type": "application/xml"}, timeout=10)
                logger.info("[NPCI] rem_bank responded %s [reqvaladd]", r.status_code)
            except requests.RequestException as e:
                logger.warning("[NPCI] rem_bank request failed [reqvaladd]: %s", e)
    return Response(
        r.content,
        status=r.status_code,
        mimetype=r.headers.get("Content-Type", "application/xml"),
    )


@app.post("/api/reqpay")
def reqpay() -> tuple[Response | dict, int]:
    """
    Receive ReqPay from Payer PSP, validate (upi_pay_request.xsd), set Txn.type=DEBIT,
    forward to remitter bank (rem_bank) to debit the payer's account, then return 202.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    ct = request.content_type or ""
    if "xml" not in ct and "application/octet-stream" not in ct:
        return jsonify(error="Content-Type must be application/xml or text/xml"), 415
    try:
        _validate_reqpay(request.data)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # Debug: request body (use logger so it shows in: docker compose logs -f npci)
    try:
        logger.info("[NPCI] /api/reqpay received body (first 500 chars): %s", (request.data or b"")[:500].decode("utf-8", errors="replace"))
    except Exception:
        logger.info("[NPCI] /api/reqpay received body len=%s", len(request.data or b""))
    # Forward ReqPay with Txn.type=DEBIT to remitter bank to debit payer's account
    to_rem = _reqpay_as_debit(request.data)
    if to_rem:
        # Log what we're sending to rem_bank for debugging
        try:
            logger.info("[NPCI] /api/reqpay sending to rem_bank (first 500 chars): %s", to_rem[:500].decode("utf-8", errors="replace"))
        except Exception:
            logger.info("[NPCI] /api/reqpay sending to rem_bank len=%s", len(to_rem))
        
        # Store ReqPay fields so when RespPay DEBIT arrives we can build ReqPay CREDIT for bene_bank
        info = _parse_reqpay_fields(request.data)
        if info:
            _pending_debits[info["msgId"]] = info
            logger.info("[NPCI] Stored pending debit info: payer_code=%s, payee_code=%s", info.get("payer_code"), info.get("payee_code"))
        url = f"{REM_BANK_URL.rstrip('/')}/api/reqpay"
        logger.info("[NPCI] Forwarding ReqPay (DEBIT) to rem_bank: %s", url)
        try:
            r = requests.post(url, data=to_rem, headers={"Content-Type": "application/xml"}, timeout=10)
            logger.info("[NPCI] rem_bank responded %s", r.status_code)
            
            # Propagate synchronous errors (like validation rejections)
            if r.status_code >= 400:
                logger.info("[NPCI] Propagating synchronous error from rem_bank: %s", r.status_code)
                return Response(
                    r.content,
                    status=r.status_code,
                    mimetype=r.headers.get("Content-Type", "application/json")
                )
        except requests.RequestException as e:
            logger.warning("[NPCI] rem_bank request failed: %s", e)
            return jsonify(error="REM_BANK_UNREACHABLE", details=str(e)), 502
    else:
        logger.warning("[NPCI] ReqPay as DEBIT is empty, skipping forward to rem_bank")
        return jsonify(error="INVALID_REQUEST", details="Could not build debit message"), 400
    return jsonify(status="accepted"), 202


@app.post("/api/resppay")
def resppay() -> tuple[dict, int]:
    """
    Receive RespPay from rem_bank (DEBIT) or bene_bank (CREDIT). Validate
    (upi_resppay_response.xsd). If DEBIT+SUCCESS: forward ReqPay CREDIT to bene_bank.
    If DEBIT+FAILURE (e.g. INSUFFICIENT_BALANCE): send final RespPay to Payer PSP with result=FAILURE.
    If CREDIT+SUCCESS: send final RespPay to Payer PSP with result=SUCCESS.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    ct = request.content_type or ""
    if "xml" not in ct and "application/octet-stream" not in ct:
        return jsonify(error="Content-Type must be application/xml or text/xml"), 415
    try:
        _validate_resppay(request.data)
    except ValueError as e:
        return jsonify(error=str(e)), 400

    # On RespPay DEBIT success: send ReqPay CREDIT to beneficiary bank
    pr = _parse_resppay(request.data)
    if pr:
        logger.info("[NPCI] Received RespPay: reqMsgId=%s | result=%s | txnType=%s", pr.get("reqMsgId"), pr.get("result"), pr.get("txnType"))
    
    if pr and (pr.get("result") or "").upper() == "SUCCESS" and (pr.get("txnType") or "").upper() == "DEBIT":
        req_msg_id = pr.get("reqMsgId")
        info = _pending_debits.pop(req_msg_id, None) if req_msg_id else None
        if info and (info.get("payee_addr") or "").strip():
            cred = _build_reqpay_credit(info)
            url = f"{BENE_BANK_URL.rstrip('/')}/api/reqpay"
            logger.info("[NPCI] Forwarding ReqPay (CREDIT) to bene_bank: %s | Payee=%s | Amount=%s | Payer.code=%s | Payee.code=%s", 
                        url, info.get("payee_addr"), info.get("amount"), info.get("payer_code"), info.get("payee_code"))
            # Log what we're sending to bene_bank for debugging
            try:
                logger.info("[NPCI] ReqPay CREDIT XML (first 500 chars): %s", cred[:500].decode("utf-8", errors="replace"))
            except Exception:
                logger.info("[NPCI] ReqPay CREDIT XML len=%s", len(cred))
            try:
                r = requests.post(url, data=cred, headers={"Content-Type": "application/xml"}, timeout=10)
                logger.info("[NPCI] bene_bank responded %s", r.status_code)
            except requests.RequestException as e:
                logger.warning("[NPCI] bene_bank request failed: %s", e)
        elif info:
             logger.warning("[NPCI] RespPay DEBIT success but payee_addr empty in info, skipping ReqPay CREDIT to bene_bank")
        else:
            logger.warning("[NPCI] RespPay DEBIT success but no pending debit found for reqMsgId: %s. Available keys: %s", req_msg_id, list(_pending_debits.keys()))
    elif pr and (pr.get("txnType") or "").upper() == "DEBIT" and (pr.get("result") or "").upper() == "FAILURE":
        # RespPay DEBIT failure (e.g. INSUFFICIENT_BALANCE): send final RespPay to Payer PSP with result=FAILURE; do not forward to bene_bank
        req_msg_id = pr.get("reqMsgId")
        _pending_debits.pop(req_msg_id, None) if req_msg_id else None
        # ReqPay flow: reqMsgId is the original (e.g. "pay-1"). reqvaladd flow: reqMsgId is "debit-msg-1". Only ReqPay has Payer PSP to notify.
        if req_msg_id and not req_msg_id.startswith("debit-"):
            txn_id = pr.get("txnId") or "final-txn"
            err_code = pr.get("errCode") or "INSUFFICIENT_BALANCE"
            final_bytes = _build_resppay_final(req_msg_id, txn_id, result="FAILURE", err_code=err_code)
            url = f"{PAYER_PSP_URL.rstrip('/')}/api/resppay"
            logger.info("[NPCI] Sending final RespPay (FAILURE) to Payer PSP: %s | reqMsgId=%s | errCode=%s", url, req_msg_id, err_code)
            try:
                r = requests.post(url, data=final_bytes, headers={"Content-Type": "application/xml"}, timeout=10)
                logger.info("[NPCI] Payer PSP responded %s (final RespPay FAILURE)", r.status_code)
            except requests.RequestException as e:
                logger.warning("[NPCI] Payer PSP request failed (final RespPay FAILURE): %s", e)
    elif pr and (pr.get("txnType") or "").upper() == "CREDIT":
        logger.info("[NPCI] Received RespPay CREDIT from bene_bank | reqMsgId=%s | result=%s", pr.get("reqMsgId"), pr.get("result"))
        # On RespPay CREDIT success: send final RespPay to Payer PSP (ReqPay flow only; skip when credit-debit-* from reqvaladd)
        req_msg_id = pr.get("reqMsgId") or ""
        if (pr.get("result") or "").upper() == "SUCCESS" and req_msg_id.startswith("credit-") and not req_msg_id.startswith("credit-debit-"):
            original_req_msg_id = req_msg_id[7:]  # strip "credit-" prefix
            txn_id = pr.get("txnId") or "final-txn"
            final_bytes = _build_resppay_final(original_req_msg_id, txn_id, result="SUCCESS")
            url = f"{PAYER_PSP_URL.rstrip('/')}/api/resppay"
            logger.info("[NPCI] Sending final RespPay to Payer PSP: %s | reqMsgId=%s | result=SUCCESS", url, original_req_msg_id)
            try:
                r = requests.post(url, data=final_bytes, headers={"Content-Type": "application/xml"}, timeout=10)
                logger.info("[NPCI] Payer PSP responded %s (final RespPay)", r.status_code)
            except requests.RequestException as e:
                logger.warning("[NPCI] Payer PSP request failed (final RespPay): %s", e)

    return jsonify(status="received"), 200


# ============================================================================
# Phase 2: AI Agent Integration
# ============================================================================

# Initialize NPCI Agent (lazy initialization on first use)
_npci_agent = None

def _get_npci_agent():
    """Get NPCI Agent instance (lazy initialization)."""
    global _npci_agent
    if _npci_agent is None:
        try:
            from agents import NPCIAgent
            from llm import LLM
            
            # Try to initialize LLM, fallback to basic mode if not available
            try:
                llm = LLM(
                    model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    base_url=os.environ.get("LLM_BASE_URL"),
                )
                logger.info("[NPCI Agent] LLM initialized")
            except Exception as e:
                logger.warning(f"[NPCI Agent] LLM initialization failed: {e}, using fallback mode")
                llm = None
            
            _npci_agent = NPCIAgent(llm_instance=llm)
            logger.info(f"[NPCI Agent] Initialized: {_npci_agent.agent_name}")
        except ImportError as e:
            logger.error(f"[NPCI Agent] Failed to import agent infrastructure: {e}")
            _npci_agent = None
    return _npci_agent


@app.post("/api/agent/create-manifest")
def create_manifest_endpoint():
    """Create and dispatch a change manifest (NPCI only)."""
    agent = _get_npci_agent()
    if not agent:
        return jsonify(error="NPCI Agent not available"), 503
    
    data = request.json
    if not data:
        return jsonify(error="Missing request body"), 400
    
    try:
        from manifest import ChangeType
        
        manifest = agent.create_manifest(
            description=data.get("description", ""),
            change_type=ChangeType(data.get("change_type", "api_change")),
            affected_components=data.get("affected_components", []),
            code_changes=data.get("code_changes", {}),
            test_requirements=data.get("test_requirements", []),
        )
        
        # Register with orchestrator FIRST so we can track the change
        receivers = data.get("receivers", [])
        if receivers:
            try:
                from a2a_protocol import A2AClient
                orchestrator_url = A2AClient.get_service_url("ORCHESTRATOR")
                if orchestrator_url:
                    requests.post(
                        f"{orchestrator_url}/api/orchestrator/register",
                        json={"manifest": manifest.to_dict(), "receivers": receivers},
                        timeout=5,
                    )
                    logger.info(f"[NPCI Agent] Registered change {manifest.change_id} with orchestrator at {orchestrator_url}")
            except Exception as e:
                logger.warning(f"[NPCI Agent] Failed to register with orchestrator: {e}")
            
            # Update status: Processing prompt
            try:
                from a2a_protocol import A2AClient
                orchestrator_url = A2AClient.get_service_url("ORCHESTRATOR")
                if orchestrator_url:
                    status_payload = {
                        "change_id": manifest.change_id,
                        "agent_id": "NPCI_AGENT",
                        "status": "RECEIVED",
                        "details": f"Processing prompt: '{data.get('description', '')[:100]}'"
                    }
                    requests.post(
                        f"{orchestrator_url}/api/orchestrator/status",
                        json=status_payload,
                        timeout=2,
                    )
                    logger.info(f"[NPCI Agent] Updated status for {manifest.change_id} at {orchestrator_url}")
            except Exception as e:
                logger.warning(f"[NPCI Agent] Failed to update status: {e}")
        
        # Dispatch to receivers
        if receivers:
            logger.info(f"[NPCI Agent] Dispatching manifest {manifest.change_id} to {len(receivers)} agents: {', '.join(receivers)}")
            
            # Update status: Dispatching
            try:
                from a2a_protocol import A2AClient
                orchestrator_url = A2AClient.get_service_url("ORCHESTRATOR")
                if orchestrator_url:
                    dispatch_payload = {
                        "change_id": manifest.change_id,
                        "agent_id": "NPCI_AGENT",
                        "status": "APPLIED",
                        "details": f"Dispatching to agents: {', '.join(receivers)}"
                    }
                    requests.post(
                        f"{orchestrator_url}/api/orchestrator/status",
                        json=dispatch_payload,
                        timeout=2,
                    )
                    logger.info(f"[NPCI Agent] Updated dispatch status for {manifest.change_id} at {orchestrator_url}")
            except Exception as e:
                logger.warning(f"[NPCI Agent] Failed to update status: {e}")
            
            dispatch_results = agent.dispatch_manifest(manifest, receivers)
            
            logger.info(f"[NPCI Agent] Dispatch results: {dispatch_results}")
            
            return jsonify({
                "status": "created_and_dispatched",
                "change_id": manifest.change_id,
                "manifest": manifest.to_dict(),
                "dispatch_results": dispatch_results,
            }), 200
        else:
            return jsonify({
                "status": "created",
                "change_id": manifest.change_id,
                "manifest": manifest.to_dict(),
            }), 200
            
    except Exception as e:
        logger.error(f"[NPCI Agent] Error creating manifest: {e}")
        return jsonify(error=str(e)), 500


@app.post("/api/agent/manifest")
def receive_manifest_endpoint():
    """Receive manifest via A2A protocol."""
    agent = _get_npci_agent()
    if not agent:
        return jsonify(error="NPCI Agent not available"), 503
    
    data = request.json
    if not data:
        return jsonify(error="Missing request body"), 400
    
    try:
        from manifest import ChangeManifest
        
        # Extract manifest from A2A message payload
        payload = data.get("payload", {})
        manifest_dict = payload.get("manifest", {})
        
        if not manifest_dict:
            return jsonify(error="Missing manifest in payload"), 400
        
        manifest = ChangeManifest.from_dict(manifest_dict)
        result = agent.receive_manifest(manifest)
        
        return jsonify(result), 200
        
    except Exception as e:
        logger.error(f"[NPCI Agent] Error receiving manifest: {e}")
        return jsonify(error=str(e)), 500


@app.get("/api/agent/status/<change_id>")
def get_agent_status(change_id: str):
    """Get agent status for a specific change."""
    agent = _get_npci_agent()
    if not agent:
        return jsonify(error="NPCI Agent not available"), 503
    
    status = agent.get_status(change_id)
    if status:
        return jsonify(status), 200
    return jsonify(error="Change not found"), 404


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    logger.info("[NPCI] Starting on 0.0.0.0:%s (logs go to stderr -> docker compose logs)", port)
    app.run(host="0.0.0.0", port=port)

