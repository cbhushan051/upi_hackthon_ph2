import logging
import os
import xml.etree.ElementTree as ET
import requests
from flask import Flask, jsonify, request, Response

from db.db import init_db, seed_sample_users, User

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [payer_psp] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
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
NPCI_URL = os.environ.get("NPCI_URL", "http://npci:5000")
_session_factory = None


def _qname(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _startup() -> None:
    global _session_factory
    _session_factory = init_db()
    with _session_factory() as session:
        seed_sample_users(session)


def _ensure_session():
    global _session_factory
    if _session_factory is None:
        _startup()


@app.get("/health")
def health() -> tuple[dict, int]:
    return jsonify(status="ok"), 200


@app.post("/api/reqvaladd")
def reqvaladd() -> tuple[Response | dict, int]:
    """
    Forward ReqValAdd to NPCI; receive RespValAdd from NPCI (routed by NPCI from Payee PSP)
    and return to client. Req: upi_req_valadd.xsd; Resp: upi_resp_valadd.xsd.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    ct = request.content_type or ""
    if "xml" not in ct and "application/octet-stream" not in ct:
        return jsonify(error="Content-Type must be application/xml or text/xml"), 415
    try:
        r = requests.post(
            f"{NPCI_URL.rstrip('/')}/api/reqvaladd",
            data=request.data,
            headers={"Content-Type": "application/xml"},
            timeout=120,
        )
    except requests.RequestException as e:
        return jsonify(error=f"NPCI unreachable: {e}"), 502
    return Response(
        r.content,
        status=r.status_code,
        mimetype=r.headers.get("Content-Type", "application/xml"),
    )


@app.post("/api/reqpay")
def reqpay() -> tuple[Response | dict, int]:
    """
    Forward ReqPay XML to NPCI.
    Note: PIN validation is also performed at the remitter bank.
    Schema: common/schemas/upi_pay_request.xsd
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    ct = request.content_type or ""
    if "xml" not in ct and "application/octet-stream" not in ct:
        return jsonify(error="Content-Type must be application/xml or text/xml"), 415
    
    _ensure_session()
    
    # Forward the XML as is (including Creds for remitter bank verification)
    try:
        root = ET.fromstring(request.data)
        q = lambda n: f".//{{{NS}}}{n}"
        
        # Extract payer VPA, PIN, and Amount
        payer = root.find(q("Payer"))
        if payer is None:
            return jsonify(error="Invalid ReqPay: missing Payer element"), 400
        
        payer_vpa = (payer.get("addr") or "").strip()
        if not payer_vpa:
            return jsonify(error="Invalid ReqPay: missing Payer.addr"), 400

        # Extract Amount
        amt_el = payer.find(q("Amount"))
        if amt_el is None:
            return jsonify(error="Invalid ReqPay: missing Amount element"), 400
        amount = float(amt_el.get("value") or 0)
        
        # Extract PIN from Creds
        provided_pin = None
        creds = payer.find(q("Creds"))
        if creds is not None:
            cred = creds.find(q("Cred"))
            if cred is not None and cred.get("type") == "PIN":
                data = cred.find(q("Data"))
                if data is not None and data.text:
                    provided_pin = data.text.strip()
        
        if not provided_pin:
            logger.info(f"[payer_psp] Validation failed: PIN not provided for {payer_vpa}")
            return jsonify(error="MISSING_PIN", details="UPI PIN is required"), 400

        # Validate PIN against DB
        with _session_factory() as session:
            user = session.query(User).filter_by(vpa=payer_vpa).one_or_none()
            if not user:
                logger.info(f"[payer_psp] Validation failed: User not found for VPA {payer_vpa}")
                return jsonify(error="PAYER_NOT_FOUND"), 400
            
            if user.pin != provided_pin:
                logger.info(f"[payer_psp] Validation failed: Incorrect PIN for {payer_vpa}")
                return jsonify(error="INVALID_PIN", details="The entered UPI PIN is incorrect"), 400

        # Log Payer.code before forwarding for debugging
        payer_code = payer.get("code") if payer is not None else None
        payees_elem = root.find(q("Payees"))
        payee_elem = payees_elem.find(f"{{{NS}}}Payee") if payees_elem is not None else None
        payee_code = payee_elem.get("code") if payee_elem is not None else None
        logger.info(f"[payer_psp] Validated ReqPay for {payer_vpa} | Amount: {amount} | PIN: OK | Payer.code={payer_code} | Payee.code={payee_code}")
        
        # Forward the ORIGINAL XML to preserve all attributes exactly as received
        # Don't re-serialize as that can lose namespace prefixes and attribute ordering
        forward_xml = request.data
        
        # Log first 500 chars of forwarded XML for debugging
        logger.info(f"[payer_psp] Forwarding ORIGINAL XML to NPCI (first 500 chars): {forward_xml[:500].decode('utf-8', errors='replace')}")
        
    except ET.ParseError as e:
        return jsonify(error=f"Invalid XML: {e}"), 400
    except Exception as e:
        logger.error(f"[payer_psp] Error processing ReqPay: {e}")
        return jsonify(error=f"Internal error: {e}"), 500
    
    # Forward XML to NPCI
    try:
        r = requests.post(
            f"{NPCI_URL.rstrip('/')}/api/reqpay",
            data=forward_xml,
            headers={"Content-Type": "application/xml"},
            timeout=120,
        )
    except requests.RequestException as e:
        return jsonify(error=f"NPCI unreachable: {e}"), 502
    
    return Response(
        r.content,
        status=r.status_code,
        mimetype=r.headers.get("Content-Type", "application/xml"),
    )


@app.post("/api/resppay")
def resppay() -> tuple[dict, int]:
    """
    Receive final RespPay from NPCI: transaction completed (debit at rem_bank, credit at bene_bank).
    Schema: common/schemas/upi_resppay_response.xsd. Accept and return 200.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    # Optional: parse for logging
    try:
        root = ET.fromstring(request.data)
        def q(tag):
            return f".//{{{NS}}}{tag}"
        resp = root.find(q("Resp"))
        txn = root.find(q("Txn"))
        req_msg_id = resp.get("reqMsgId") if resp is not None else None
        result = resp.get("result") if resp is not None else None
        txn_type = txn.get("type") if txn is not None else None
        logger.info("[payer_psp] Received final RespPay from NPCI | reqMsgId=%s | result=%s | Txn.type=%s", req_msg_id, result, txn_type)
    except (ET.ParseError, AttributeError):
        logger.info("[payer_psp] Received RespPay from NPCI (parse skipped)")
    return jsonify(status="received", result="SUCCESS"), 200


if __name__ == "__main__":
    _startup()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
