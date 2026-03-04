"""
Payment UI - GPay-like interface for UPI transaction simulation
"""
import logging
import os
import xml.etree.ElementTree as ET
import xml.sax.saxutils as saxutils
from datetime import datetime
from flask import Flask, jsonify, request, send_from_directory
import requests
import xml.dom.minidom

import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [payment_ui] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Set Flask's werkzeug logger to INFO to see all HTTP requests
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)

app = Flask(__name__, static_folder='static', static_url_path='/static')


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

# Configuration
NS = "http://npci.org/upi/schema/"
PAYER_PSP_URL = os.environ.get("PAYER_PSP_URL", "http://localhost:6004")

# Sample contacts - in a real app, these would come from a database
CONTACTS = [
    {"vpa": "Chandra@phonepe", "name": "Chandra", "avatar": "👨", "bank": "PhonePe"},
    {"vpa": "Gaurang@phonepe", "name": "Gaurang", "avatar": "👤", "bank": "PhonePe"},
    {"vpa": "Hrithik@phonepe", "name": "Hrithik", "avatar": "🧑", "bank": "PhonePe"},
]

PAYER_USERS = [
    {"vpa": "Chandra@paytm", "name": "Chandra", "pin": "1111", "balance": 10000.00},
    {"vpa": "Gaurang@paytm", "name": "Gaurang", "pin": "1111", "balance": 15000.00},
    {"vpa": "Hrithik@paytm", "name": "Hrithik", "pin": "1111", "balance": 20000.00},
]

# Map payee VPA (e.g. Hrithik@phonepe) to same person's payer VPA (Hrithik@paytm) for balance update
PAYEE_VPA_TO_PAYER_VPA = {
    "Chandra@phonepe": "Chandra@paytm",
    "Gaurang@phonepe": "Gaurang@paytm",
    "Hrithik@phonepe": "Hrithik@paytm",
}


def _update_balances_on_success(payer_vpa: str, payee_vpa: str, amount: float) -> None:
    """Update PAYER_USERS balances after a successful transaction. Payer debited, payee credited."""
    for u in PAYER_USERS:
        if u["vpa"] == payer_vpa:
            u["balance"] = round(u["balance"] - amount, 2)
        payer_vpa_for_payee = PAYEE_VPA_TO_PAYER_VPA.get(payee_vpa)
        if payer_vpa_for_payee and u["vpa"] == payer_vpa_for_payee:
            u["balance"] = round(u["balance"] + amount, 2)


def _qname(tag: str) -> str:
    """Generate qualified XML tag name with namespace."""
    return f"{{{NS}}}{tag}"


def prettify_xml(xml_string: str) -> str:
    """Format XML string with proper indentation."""
    try:
        dom = xml.dom.minidom.parseString(xml_string if isinstance(xml_string, bytes) else xml_string.encode())
        return dom.toprettyxml(indent="  ")
    except Exception:
        return xml_string


def _get_txn_purpose_from_reqpay(xml_str: str | bytes) -> str | None:
    """Extract Txn.purpose from ReqPay XML (upi_pay_request.xsd). Returns None on parse error or if missing."""
    try:
        raw = xml_str.encode() if isinstance(xml_str, str) else xml_str
        root = ET.fromstring(raw)
        txn = root.find(f".//{{{NS}}}Txn")
        return (txn.get("purpose") or "").strip() or None if txn is not None else None
    except Exception:
        return None


def build_reqpay_debit_xml(txn_id: str, msg_id: str, payer_vpa: str, amount: float, payer_code: str = "0000", purpose: str | None = "PAY") -> str:
    """Build ReqPay DEBIT XML (NPCI → Remitter Bank). Per upi_pay_request.xsd Txn.purpose is optional."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    purpose_attr = f' purpose="{purpose}"' if purpose else ""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ns:ReqPay xmlns:ns="{NS}">
  <ns:Head ver="2.0" ts="{ts}" orgId="NPCI" msgId="DEBIT-{msg_id}" prodType="UPI"/>
  <ns:Txn id="{txn_id}" note="UPI Payment" type="DEBIT" ts="{ts}"{purpose_attr}/>
  <ns:Payer addr="{payer_vpa}" name="Payer Name" seqNum="1" type="PERSON" code="{payer_code}">
    <ns:Amount value="{amount:.2f}" curr="INR"/>
  </ns:Payer>
</ns:ReqPay>'''


def _escape_attr(s: str) -> str:
    """Escape string for use in an XML attribute value (per XML 1.0)."""
    if not s:
        return s
    return saxutils.escape(s, {"'": "&apos;", '"': "&quot;"})


def build_resppay_debit_xml(txn_id: str, msg_id: str, result: str = "SUCCESS", bal_amt: float = None, err_code: str | None = None) -> str:
    """Build RespPay DEBIT XML (Remitter Bank → NPCI). Per common/schemas/upi_resppay_response.xsd."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    bal_ref = f'\n    <ns:Ref balAmt="{bal_amt:.2f}"/>' if bal_amt is not None else ''
    err_attr = f' errCode="{_escape_attr(err_code)}"' if err_code else ''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ns:RespPay xmlns:ns="{NS}">
  <ns:Head ver="2.0" ts="{ts}" orgId="REM_BANK" msgId="resppay-debit-{msg_id}" prodType="UPI"/>
  <ns:Txn id="{txn_id}" type="DEBIT"/>
  <ns:Resp reqMsgId="{msg_id}" result="{result}"{err_attr}>{bal_ref}
  </ns:Resp>
</ns:RespPay>'''


def build_reqpay_credit_xml(txn_id: str, msg_id: str, payer_vpa: str, payee_vpa: str, amount: float, payer_code: str = "0000", payee_code: str = "0000", purpose: str | None = "PAY") -> str:
    """Build ReqPay CREDIT XML (NPCI → Beneficiary Bank). Per upi_pay_request.xsd Txn.purpose is optional."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    purpose_attr = f' purpose="{purpose}"' if purpose else ""
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ns:ReqPay xmlns:ns="{NS}">
  <ns:Head ver="2.0" ts="{ts}" orgId="NPCI" msgId="CREDIT-{msg_id}" prodType="UPI"/>
  <ns:Txn id="{txn_id}" note="UPI Payment" type="CREDIT" ts="{ts}"{purpose_attr}/>
  <ns:Payer addr="{payer_vpa}" name="Payer Name" seqNum="1" type="PERSON" code="{payer_code}">
    <ns:Amount value="{amount:.2f}" curr="INR"/>
  </ns:Payer>
  <ns:Payees>
    <ns:Payee addr="{payee_vpa}" name="Payee Name" seqNum="1" type="PERSON" code="{payee_code}">
      <ns:Amount value="{amount:.2f}" curr="INR"/>
    </ns:Payee>
  </ns:Payees>
</ns:ReqPay>'''


def build_resppay_credit_xml(txn_id: str, msg_id: str, result: str = "SUCCESS", bal_amt: float = None, err_code: str | None = None) -> str:
    """Build RespPay CREDIT XML (Beneficiary Bank → NPCI). Per common/schemas/upi_resppay_response.xsd."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    bal_ref = f'\n    <ns:Ref balAmt="{bal_amt:.2f}"/>' if bal_amt is not None else ''
    err_attr = f' errCode="{_escape_attr(err_code)}"' if err_code else ''
    return f'''<?xml version="1.0" encoding="UTF-8"?>
<ns:RespPay xmlns:ns="{NS}">
  <ns:Head ver="2.0" ts="{ts}" orgId="BENE_BANK" msgId="resppay-credit-{msg_id}" prodType="UPI"/>
  <ns:Txn id="{txn_id}" type="CREDIT"/>
  <ns:Resp reqMsgId="CREDIT-{msg_id}" result="{result}"{err_attr}>{bal_ref}
  </ns:Resp>
</ns:RespPay>'''


def build_reqpay_xml(payer_vpa: str, payee_vpa: str, amount: float, pin: str, purpose: str | None = "PAY") -> tuple[bytes, str, str]:
    """Build ReqPay XML message for UPI payment. Returns (xml_bytes, txn_id, msg_id). Per upi_pay_request.xsd Txn.purpose is optional."""
    ts = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    txn_id = f"TXN{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}"
    msg_id = f"MSG{datetime.utcnow().strftime('%Y%m%d%H%M%S%f')[:-3]}"
    
    root = ET.Element(_qname("ReqPay"))
    
    # Head
    head = ET.SubElement(root, _qname("Head"))
    head.set("ver", "2.0")
    head.set("ts", ts)
    head.set("orgId", "PAYER_PSP")
    head.set("msgId", msg_id)
    head.set("prodType", "UPI")
    
    # Txn (purpose is optional in upi_pay_request.xsd TxnType)
    txn = ET.SubElement(root, _qname("Txn"))
    txn.set("id", txn_id)
    txn.set("note", "UPI Payment")
    txn.set("type", "PAY")
    txn.set("ts", ts)
    if purpose:
        txn.set("purpose", purpose)
    
    # Payer
    payer = ET.SubElement(root, _qname("Payer"))
    payer.set("addr", payer_vpa)
    payer.set("name", "Payer Name")
    payer.set("seqNum", "1")
    payer.set("type", "PERSON")
    payer.set("code", "0000")
    
    # Payer Credentials (PIN) - MUST COME BEFORE AMOUNT per XSD schema
    creds = ET.SubElement(payer, _qname("Creds"))
    cred = ET.SubElement(creds, _qname("Cred"))
    cred.set("type", "PIN")
    cred_data = ET.SubElement(cred, _qname("Data"))
    cred_data.text = pin
    
    # Payer Amount - MUST COME AFTER CREDS per XSD schema
    payer_amount = ET.SubElement(payer, _qname("Amount"))
    payer_amount.set("value", f"{amount:.2f}")
    payer_amount.set("curr", "INR")
    
    # Payees
    payees = ET.SubElement(root, _qname("Payees"))
    payee = ET.SubElement(payees, _qname("Payee"))
    payee.set("addr", payee_vpa)
    payee.set("name", "Payee Name")
    payee.set("seqNum", "1")
    payee.set("type", "PERSON")
    payee.set("code", "0000")
    
    # Payee Amount
    payee_amount = ET.SubElement(payee, _qname("Amount"))
    payee_amount.set("value", f"{amount:.2f}")
    payee_amount.set("curr", "INR")
    
    xml_str = ET.tostring(root, encoding="unicode", method="xml")
    full_xml = '<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str
    return full_xml.encode("utf-8"), txn_id, msg_id


@app.route("/")
def index():
    """Serve the main UI."""
    return send_from_directory(app.static_folder, 'index.html')


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(status="ok"), 200


@app.route("/api/contacts", methods=["GET"])
def get_contacts():
    """Get list of payee contacts."""
    return jsonify(contacts=CONTACTS), 200


@app.route("/api/users", methods=["GET"])
def get_users():
    """Get list of payer users (for login/selection)."""
    # Don't send PINs to frontend
    users = [{"vpa": u["vpa"], "name": u["name"], "balance": u["balance"]} for u in PAYER_USERS]
    return jsonify(users=users), 200


@app.route("/api/preview-reqpay", methods=["POST"])
def preview_reqpay():
    """Generate and return the ReqPay XML for user review/editing before sending."""
    try:
        data = request.json
        payer_vpa = data.get("payer_vpa")
        payee_vpa = data.get("payee_vpa")
        amount = float(data.get("amount", 0))
        pin = data.get("pin")
        
        if not all([payer_vpa, payee_vpa, amount, pin]):
            return jsonify(success=False, error="Missing required fields"), 400
        
        # Validate payer exists
        payer = next((u for u in PAYER_USERS if u["vpa"] == payer_vpa), None)
        if not payer:
            return jsonify(success=False, error="Invalid payer VPA"), 400
        
        # Build the ReqPay XML
        xml_body, txn_id, msg_id = build_reqpay_xml(payer_vpa, payee_vpa, amount, pin)
        pretty_xml = prettify_xml(xml_body.decode('utf-8'))
        
        logger.info(f"Generated ReqPay preview: {payer_vpa} -> {payee_vpa}, Amount: {amount}, TxnId: {txn_id}")
        
        return jsonify(
            success=True,
            xml=pretty_xml,
            txn_id=txn_id,
            msg_id=msg_id,
            metadata={
                "payer_vpa": payer_vpa,
                "payee_vpa": payee_vpa,
                "amount": amount
            }
        ), 200
    
    except Exception as e:
        logger.error(f"Error generating ReqPay preview: {e}")
        return jsonify(success=False, error=str(e)), 500


@app.route("/api/send-edited-reqpay", methods=["POST"])
def send_edited_reqpay():
    """Send edited ReqPay XML to Payer PSP."""
    steps = []
    start_time = datetime.utcnow()
    
    def add_step(title, status, description, xml_data=None, duration_ms=None, step_type=None):
        step = {
            "title": title,
            "status": status,
            "description": description,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }
        if xml_data:
            step["xml"] = xml_data
        if duration_ms is not None:
            step["duration_ms"] = duration_ms
        if step_type:
            step["step_type"] = step_type
        steps.append(step)
    
    try:
        data = request.json
        edited_xml = data.get("xml")
        metadata = data.get("metadata", {})
        
        if not edited_xml:
            return jsonify(success=False, error="No XML provided"), 400
        
        # Parse the edited XML to extract transaction details
        try:
            root = ET.fromstring(edited_xml)
            # Extract namespace
            ns_match = edited_xml.split('xmlns:ns="')[1].split('"')[0] if 'xmlns:ns="' in edited_xml else NS
            ns_prefix = f"{{{ns_match}}}"
            
            # Extract transaction ID and message ID from XML
            txn_elem = root.find(f"{ns_prefix}Txn")
            head_elem = root.find(f"{ns_prefix}Head")
            payer_elem = root.find(f"{ns_prefix}Payer")
            payees_elem = root.find(f"{ns_prefix}Payees")
            
            if txn_elem is None or head_elem is None:
                return jsonify(success=False, error="Invalid XML structure"), 400
            
            txn_id = txn_elem.get("id")
            msg_id = head_elem.get("msgId")
            payer_vpa = payer_elem.get("addr") if payer_elem is not None else metadata.get("payer_vpa")
            
            # Extract payee VPA and code
            payee_vpa = metadata.get("payee_vpa")
            payee_code = "0000"  # Default
            if payees_elem is not None:
                payee_elem = payees_elem.find(f"{ns_prefix}Payee")
                if payee_elem is not None:
                    payee_vpa = payee_elem.get("addr")
                    payee_code = payee_elem.get("code", "0000")
            
            # Extract payer code
            payer_code = "0000"  # Default
            if payer_elem is not None:
                payer_code = payer_elem.get("code", "0000")
            
            # Extract amount
            amount = metadata.get("amount", 0)
            if payer_elem is not None:
                amt_elem = payer_elem.find(f"{ns_prefix}Amount")
                if amt_elem is not None:
                    amount = float(amt_elem.get("value", amount))
            
            logger.info(f"Extracted from edited XML: payer_code={payer_code}, payee_code={payee_code}")
            
        except Exception as e:
            logger.error(f"Error parsing edited XML: {e}")
            return jsonify(success=False, error=f"Invalid XML: {str(e)}"), 400
        
        # Step 1: XML Validation
        add_step(
            "Edited XML Validation",
            "success",
            f"User-edited ReqPay XML validated successfully (TxnId: {txn_id})",
            xml_data=edited_xml,
            step_type="validation"
        )
        
        # Step 2: Send to Payer PSP
        add_step(
            "1. Sending Edited ReqPay (UI → Payer PSP)",
            "processing",
            "Sending user-edited ReqPay XML to Payer PSP",
            step_type="reqpay"
        )
        
        # Detect PSP URL
        payer_psp_url = PAYER_PSP_URL
        try:
            import socket
            socket.gethostbyname('payer_psp')
            payer_psp_url = "http://payer_psp:6004"
        except socket.gaierror:
            pass
        
        logger.info(f"Sending edited ReqPay: {payer_vpa} -> {payee_vpa}, Amount: {amount}, TxnId: {txn_id}")
        
        # Send to Payer PSP
        try:
            req_start = datetime.utcnow()
            response = requests.post(
                f"{payer_psp_url.rstrip('/')}/api/reqpay",
                data=edited_xml.encode('utf-8'),
                headers={"Content-Type": "application/xml"},
                timeout=10
            )
            req_duration = int((datetime.utcnow() - req_start).total_seconds() * 1000)
            
            steps[-1]["status"] = "success"
            steps[-1]["description"] = f"Edited ReqPay sent to Payer PSP (TxnId: {txn_id})"
            
            # Get payer info for balance estimation
            payer = next((u for u in PAYER_USERS if u["vpa"] == payer_vpa), {"balance": 10000})
            
            if response.status_code == 202:
                # Success - show complete flow
                add_step(
                    "2. ReqPay XML (Payer PSP → NPCI)",
                    "success",
                    "Payer PSP validated and forwarded to NPCI Switch",
                    xml_data=edited_xml,
                    step_type="reqpay_npci"
                )
                
                # ReqPay DEBIT (preserve purpose from edited ReqPay per upi_pay_request.xsd)
                purpose = _get_txn_purpose_from_reqpay(edited_xml) or "PAY"
                reqpay_debit = build_reqpay_debit_xml(txn_id, msg_id, payer_vpa, amount, payer_code=payer_code, purpose=purpose)
                add_step(
                    "3. ReqPay DEBIT (NPCI → Remitter Bank)",
                    "success",
                    f"NPCI sent DEBIT request to debit ₹{amount:.2f} from {payer_vpa}",
                    xml_data=reqpay_debit,
                    step_type="reqpay_debit"
                )
                
                # RespPay DEBIT
                estimated_balance = payer.get("balance", 10000) - amount
                resppay_debit = build_resppay_debit_xml(txn_id, msg_id, "SUCCESS", estimated_balance)
                add_step(
                    "4. RespPay DEBIT (Remitter Bank → NPCI)",
                    "success",
                    f"Remitter Bank confirmed debit. Remaining balance: ₹{estimated_balance:.2f}",
                    xml_data=resppay_debit,
                    step_type="resppay_debit"
                )
                
                # ReqPay CREDIT (same purpose as DEBIT)
                reqpay_credit = build_reqpay_credit_xml(txn_id, msg_id, payer_vpa, payee_vpa, amount, payer_code=payer_code, payee_code=payee_code, purpose=purpose)
                add_step(
                    "5. ReqPay CREDIT (NPCI → Beneficiary Bank)",
                    "success",
                    f"NPCI sent CREDIT request to credit ₹{amount:.2f} to {payee_vpa}",
                    xml_data=reqpay_credit,
                    step_type="reqpay_credit"
                )
                
                # RespPay CREDIT
                resppay_credit = build_resppay_credit_xml(txn_id, msg_id, "SUCCESS", amount + 1000)
                add_step(
                    "6. RespPay CREDIT (Beneficiary Bank → NPCI)",
                    "success",
                    f"Beneficiary Bank confirmed credit to {payee_vpa}",
                    xml_data=resppay_credit,
                    step_type="resppay_credit"
                )
                
                # Final success
                total_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                add_step(
                    "Transaction Complete",
                    "success",
                    f"Payment of ₹{amount:.2f} from {payer_vpa} to {payee_vpa} completed successfully!",
                    duration_ms=total_duration,
                    step_type="complete"
                )
                # Update in-memory balances so /api/users returns correct values
                _update_balances_on_success(payer_vpa, payee_vpa, amount)
                return jsonify(
                    success=True,
                    message="Transaction successful!",
                    txn_id=txn_id,
                    status_code=response.status_code,
                    steps=steps
                ), 200
            else:
                # Handle errors (similar to create_transaction)
                error_msg = "Transaction failed"
                error_code = None
                try:
                    error_data = response.json()
                    error_msg = error_data.get("details") or error_data.get("error", "Transaction failed")
                    error_code = error_data.get("error")
                except Exception:
                    error_msg = f"Transaction failed with status {response.status_code}"
                
                payer_psp_errors = ["INVALID_PIN", "MISSING_PIN", "PAYER_NOT_FOUND"]
                remitter_bank_errors = [
                    "INSUFFICIENT_BALANCE", "MIN_AMOUNT_VIOLATION", "PAYER_ACCOUNT_NOT_FOUND",
                    "ACCOUNT_BLOCKED", "DAILY_LIMIT_EXCEEDED"
                ]
                
                if error_code in payer_psp_errors:
                    add_step("2. Validation Failed (Payer PSP)", "error", f"Payer PSP rejected: {error_msg}", step_type="error")
                elif error_code in remitter_bank_errors or error_code:
                    add_step("2. ReqPay XML (Payer PSP → NPCI)", "success", "PIN validated. Forwarded to NPCI", xml_data=edited_xml, step_type="reqpay_npci")
                    purpose = _get_txn_purpose_from_reqpay(edited_xml) or "PAY"
                    reqpay_debit = build_reqpay_debit_xml(txn_id, msg_id, payer_vpa, amount, payer_code=payer_code, purpose=purpose)
                    add_step("3. ReqPay DEBIT (NPCI → Remitter Bank)", "success", f"NPCI sent DEBIT request for ₹{amount:.2f}", xml_data=reqpay_debit, step_type="reqpay_debit")
                    resppay_debit_fail = build_resppay_debit_xml(txn_id, msg_id, result="FAILURE", err_code=error_code)
                    add_step("4. RespPay DEBIT - FAILED (Remitter Bank → NPCI)", "error", f"Remitter Bank rejected: {error_code} - {error_msg}", xml_data=resppay_debit_fail, step_type="resppay_debit")
                else:
                    add_step("Transaction Failed", "error", error_msg, step_type="error")
                
                return jsonify(success=False, error=error_msg, status_code=response.status_code, steps=steps), 200
        
        except requests.exceptions.ConnectionError:
            add_step("Connection Failed", "error", "Could not connect to Payer PSP", step_type="error")
            return jsonify(success=False, error="Connection failed", status_code=0, steps=steps), 200
        except requests.exceptions.Timeout:
            add_step("Request Timeout", "error", "Request timed out", step_type="error")
            return jsonify(success=False, error="Transaction timeout", status_code=0, steps=steps), 200
    
    except Exception as e:
        logger.error(f"Error sending edited ReqPay: {e}")
        add_step("System Error", "error", f"Internal error: {str(e)}", step_type="error")
        return jsonify(success=False, error=str(e), status_code=500, steps=steps), 200


@app.route("/api/transaction", methods=["POST"])
def create_transaction():
    """Create a new UPI transaction with detailed timeline steps showing all XMLs."""
    steps = []
    start_time = datetime.utcnow()
    
    def add_step(title, status, description, xml_data=None, duration_ms=None, step_type=None):
        step = {
            "title": title,
            "status": status,  # pending, processing, success, error
            "description": description,
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        }
        if xml_data:
            step["xml"] = xml_data
        if duration_ms is not None:
            step["duration_ms"] = duration_ms
        if step_type:
            step["step_type"] = step_type
        steps.append(step)
    
    try:
        data = request.json
        payer_vpa = data.get("payer_vpa")
        payee_vpa = data.get("payee_vpa")
        amount = float(data.get("amount", 0))
        pin = data.get("pin")
        
        # Step 1: Validate input
        add_step(
            "Input Validation",
            "processing",
            f"Validating payment details: {payer_vpa} → {payee_vpa}, Amount: ₹{amount:.2f}",
            step_type="validation"
        )
        
        if not all([payer_vpa, payee_vpa, amount, pin]):
            add_step(
                "Input Validation",
                "error",
                "Missing required fields (payer_vpa, payee_vpa, amount, or pin)"
            )
            return jsonify(success=False, error="Missing required fields", steps=steps), 200
        
        # Basic validation only - let Payer PSP handle business rules
        payer = next((u for u in PAYER_USERS if u["vpa"] == payer_vpa), None)
        if not payer:
            add_step("Input Validation", "error", f"Invalid payer VPA: {payer_vpa}")
            return jsonify(success=False, error="Invalid payer VPA", steps=steps), 200
        
        steps[-1]["status"] = "success"
        steps[-1]["description"] = "All payment details validated successfully"
        
        # Step 2: Build ReqPay XML (Payment UI → Payer PSP)
        add_step(
            "1. ReqPay XML (UI → Payer PSP)",
            "processing",
            "Building UPI ReqPay XML message with payment credentials",
            step_type="reqpay"
        )
        
        xml_body, txn_id, msg_id = build_reqpay_xml(payer_vpa, payee_vpa, amount, pin)
        pretty_req_xml = prettify_xml(xml_body.decode('utf-8'))
        
        steps[-1]["status"] = "success"
        steps[-1]["description"] = f"ReqPay built and sent to Payer PSP (TxnId: {txn_id})"
        steps[-1]["xml"] = pretty_req_xml
        
        # Detect PSP URL
        payer_psp_url = PAYER_PSP_URL
        try:
            import socket
            socket.gethostbyname('payer_psp')
            payer_psp_url = "http://payer_psp:6004"
        except socket.gaierror:
            pass
        
        logger.info(f"Sending transaction: {payer_vpa} -> {payee_vpa}, Amount: {amount}")
        
        # Step 3: Send to Payer PSP and wait for response
        try:
            req_start = datetime.utcnow()
            response = requests.post(
                f"{payer_psp_url.rstrip('/')}/api/reqpay",
                data=xml_body,
                headers={"Content-Type": "application/xml"},
                timeout=10
            )
            req_duration = int((datetime.utcnow() - req_start).total_seconds() * 1000)
            
            if response.status_code == 202:
                # Transaction successful - show the complete internal flow
                
                # Step 3: ReqPay forwarded to NPCI (Payer PSP → NPCI)
                add_step(
                    "2. ReqPay XML (Payer PSP → NPCI)",
                    "success",
                    "Payer PSP validated PIN and forwarded ReqPay to NPCI Switch",
                    xml_data=pretty_req_xml,
                    step_type="reqpay_npci"
                )
                
                # Step 4: ReqPay DEBIT (NPCI → Remitter Bank)
                reqpay_debit = build_reqpay_debit_xml(txn_id, msg_id, payer_vpa, amount)
                add_step(
                    "3. ReqPay DEBIT (NPCI → Remitter Bank)",
                    "success",
                    f"NPCI sent DEBIT request to debit ₹{amount:.2f} from {payer_vpa}",
                    xml_data=reqpay_debit,
                    step_type="reqpay_debit"
                )
                
                # Step 5: RespPay DEBIT (Remitter Bank → NPCI)
                estimated_balance = payer.get("balance", 10000) - amount
                resppay_debit = build_resppay_debit_xml(txn_id, msg_id, "SUCCESS", estimated_balance)
                add_step(
                    "4. RespPay DEBIT (Remitter Bank → NPCI)",
                    "success",
                    f"Remitter Bank confirmed debit. Remaining balance: ₹{estimated_balance:.2f}",
                    xml_data=resppay_debit,
                    step_type="resppay_debit"
                )
                
                # Step 6: ReqPay CREDIT (NPCI → Beneficiary Bank)
                reqpay_credit = build_reqpay_credit_xml(txn_id, msg_id, payer_vpa, payee_vpa, amount)
                add_step(
                    "5. ReqPay CREDIT (NPCI → Beneficiary Bank)",
                    "success",
                    f"NPCI sent CREDIT request to credit ₹{amount:.2f} to {payee_vpa}",
                    xml_data=reqpay_credit,
                    step_type="reqpay_credit"
                )
                
                # Step 7: RespPay CREDIT (Beneficiary Bank → NPCI)
                resppay_credit = build_resppay_credit_xml(txn_id, msg_id, "SUCCESS", amount + 1000)  # Simulated new balance
                add_step(
                    "6. RespPay CREDIT (Beneficiary Bank → NPCI)",
                    "success",
                    f"Beneficiary Bank confirmed credit to {payee_vpa}",
                    xml_data=resppay_credit,
                    step_type="resppay_credit"
                )
                
                # Final success step
                total_duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                add_step(
                    "Transaction Complete",
                    "success",
                    f"Payment of ₹{amount:.2f} from {payer_vpa} to {payee_vpa} completed successfully!",
                    duration_ms=total_duration,
                    step_type="complete"
                )
                # Update in-memory balances so /api/users returns correct values
                _update_balances_on_success(payer_vpa, payee_vpa, amount)
                return jsonify(
                    success=True,
                    message="Transaction successful!",
                    txn_id=txn_id,
                    status_code=response.status_code,
                    steps=steps
                ), 200
            else:
                # Transaction failed - show where it failed
                error_msg = "Transaction failed"
                error_code = None
                try:
                    error_data = response.json()
                    error_msg = error_data.get("details") or error_data.get("error", "Transaction failed")
                    error_code = error_data.get("error")
                except Exception:
                    error_msg = f"Transaction failed with status {response.status_code}"
                
                # Errors that occur at Payer PSP (before forwarding to NPCI)
                payer_psp_errors = ["INVALID_PIN", "MISSING_PIN", "PAYER_NOT_FOUND"]
                
                # Errors that occur at Remitter Bank (after NPCI forwards the debit request)
                remitter_bank_errors = [
                    "INSUFFICIENT_BALANCE", 
                    "MIN_AMOUNT_VIOLATION",
                    "PAYER_ACCOUNT_NOT_FOUND",
                    "ACCOUNT_BLOCKED",
                    "DAILY_LIMIT_EXCEEDED"
                ]
                
                if error_code in payer_psp_errors:
                    # Error at Payer PSP - before forwarding to NPCI
                    add_step(
                        "2. Validation Failed (Payer PSP)",
                        "error",
                        f"Payer PSP rejected: {error_msg}",
                        step_type="error"
                    )
                elif error_code in remitter_bank_errors or error_code:
                    # Error at Remitter Bank - show flow up to the failure point
                    # Step: Payer PSP → NPCI (success - PIN was validated)
                    add_step(
                        "2. ReqPay XML (Payer PSP → NPCI)",
                        "success",
                        "PIN validated. Forwarded to NPCI Switch",
                        xml_data=pretty_req_xml,
                        step_type="reqpay_npci"
                    )
                    
                    # Step: NPCI → Remitter Bank (success - request was sent)
                    reqpay_debit = build_reqpay_debit_xml(txn_id, msg_id, payer_vpa, amount)
                    add_step(
                        "3. ReqPay DEBIT (NPCI → Remitter Bank)",
                        "success",
                        f"NPCI sent DEBIT request for ₹{amount:.2f}",
                        xml_data=reqpay_debit,
                        step_type="reqpay_debit"
                    )
                    
                    # Step: Remitter Bank → NPCI (FAILED - with error response XML, per upi_resppay_response.xsd)
                    resppay_debit_fail = build_resppay_debit_xml(txn_id, msg_id, result="FAILURE", err_code=error_code)
                    add_step(
                        "4. RespPay DEBIT - FAILED (Remitter Bank → NPCI)",
                        "error",
                        f"Remitter Bank rejected: {error_code} - {error_msg}",
                        xml_data=resppay_debit_fail,
                        step_type="resppay_debit"
                    )
                else:
                    # Unknown error - show generic failure
                    add_step(
                        "Transaction Failed",
                        "error",
                        error_msg,
                        step_type="error"
                    )
                
                return jsonify(
                    success=False,
                    error=error_msg,
                    status_code=response.status_code,
                    steps=steps
                ), 200
        
        except requests.exceptions.ConnectionError:
            add_step(
                "Connection Failed",
                "error",
                "Could not connect to Payer PSP. Make sure services are running (docker-compose up -d)",
                step_type="error"
            )
            return jsonify(
                success=False,
                error="Connection failed. Make sure services are running (docker-compose up -d)",
                status_code=0,
                steps=steps
            ), 200
        except requests.exceptions.Timeout:
            add_step(
                "Request Timeout",
                "error",
                "Request timed out after 10 seconds",
                step_type="error"
            )
            return jsonify(
                success=False,
                error="Transaction timeout. Please try again.",
                status_code=0,
                steps=steps
            ), 200
    
    except Exception as e:
        logger.error(f"Transaction error: {e}")
        add_step("System Error", "error", f"Internal error: {str(e)}", step_type="error")
        return jsonify(
            success=False,
            error=f"Internal error: {str(e)}",
            status_code=500,
            steps=steps
        ), 200


if __name__ == "__main__":
    port = int(os.environ.get("PAYMENT_UI_PORT", 8882))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    
    logger.info(f"[Payment UI] Starting on 0.0.0.0:{port}")
    logger.info(f"[Payment UI] Payer PSP URL: {PAYER_PSP_URL}")
    logger.info(f"[Payment UI] Debug mode: {debug_mode}")
    
    try:
        app.run(host="0.0.0.0", port=port, debug=debug_mode)
    except Exception as e:
        logger.error(f"[Payment UI] Failed to start: {e}")
        raise
