import logging
import os
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

# Minimum allowed transaction amount (INR) for any UPI transaction – as per latest policy the minimum value for **all** UPI transactions is 20 ₹
MIN_TRANSACTION_AMOUNT = 20.0

from db import get_account_by_vpa, init_db, seed_sample_accounts

import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [bene_bank] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr
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
        seed_sample_accounts(session)


def _ensure_session() -> None:
    global _session_factory
    if _session_factory is None:
        _startup()


@app.get("/health")
def health() -> tuple[dict, int]:
    return jsonify(status="ok"), 200


def _parse_reqpay_credit(body: bytes) -> dict | None:
    """Extract Head.msgId, Txn.id, Txn.type, Payee.addr, Payer/Amount.value, ver, prodType, payer_code, payee_code for CREDIT and RespPay."""
    try:
        root = ET.fromstring(body)
        def q(tag):
            return f".//{{{NS}}}{tag}"
        head = root.find(q("Head"))
        txn = root.find(q("Txn"))
        payer = root.find(q("Payer"))
        payees = root.find(q("Payees"))
        payee = payees.find(q("Payee")) if payees is not None else None
        amt = payer.find(q("Amount")) if payer is not None else None
        if head is None or txn is None or payee is None:
            return None
        msg_id = (head.get("msgId") or "").strip()
        if not msg_id:
            return None
        amount = float(amt.get("value") or 0) if amt is not None else 0.0
        # Validation: Minimum transaction amount of INR 1 (per manifest 73b751d3-078b-4e2c-a331-5a01ec5c6755)
        if amount < 1.0:
            return None  # Reject transactions below minimum amount
        # Validation: Minimum transaction amount of INR 20 (per new policy)
        if amount < MIN_TRANSACTION_AMOUNT:
            return None  # Reject transactions below minimum amount
        
        # Extract Payer attributes
        payer_code = (payer.get("code") or "").strip() if payer is not None else ""
        payer_type = (payer.get("type") or "").strip() if payer is not None else ""
        payer_seqNum = (payer.get("seqNum") or "").strip() if payer is not None else ""
        payer_name = (payer.get("name") or "").strip() if payer is not None else ""
        payer_addr = (payer.get("addr") or "").strip() if payer is not None else ""
        
        # Extract Payee attributes
        payee_code = (payee.get("code") or "").strip()
        payee_type = (payee.get("type") or "").strip()
        payee_seqNum = (payee.get("seqNum") or "").strip()
        payee_name = (payee.get("name") or "").strip()
        
        # Log extracted code attributes for debugging
        logger.info("[bene_bank] Parsed Payer.code=%s, Payee.code=%s, Payer.type=%s, Payee.type=%s",
                    payer_code, payee_code, payer_type, payee_type)
        
        return {
            "msgId": msg_id,
            "txnId": (txn.get("id") or "").strip(),
            "txn_type": (txn.get("type") or "").strip(),
            "payee_addr": (payee.get("addr") or "").strip(),
            "amount": amount,
            "ver": (head.get("ver") or "2.0").strip(),
            "prodType": (head.get("prodType") or "UPI").strip(),
            # Payer attributes
            "payer_addr": payer_addr,
            "payer_code": payer_code or None,
            "payer_type": payer_type or None,
            "payer_seqNum": payer_seqNum or None,
            "payer_name": payer_name or None,
            # Payee attributes
            "payee_code": payee_code or None,
            "payee_type": payee_type or None,
            "payee_seqNum": payee_seqNum or None,
            "payee_name": payee_name or None,
        }
    except (ET.ParseError, AttributeError, ValueError, TypeError):
        return None


def _build_resppay_credit(parsed: dict, result: str, err_code: str | None = None, bal_amt: float | None = None) -> bytes:
    """Build RespPay with Txn.type=CREDIT per common/schemas/upi_resppay_response.xsd."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req_msg = parsed.get("msgId") or "req"
    root = ET.Element(_qname("RespPay"))

    h = ET.SubElement(root, _qname("Head"))
    h.set("ver", parsed.get("ver") or "2.0")
    h.set("ts", ts)
    h.set("orgId", "BENE_BANK")
    h.set("msgId", f"resppay-credit-{req_msg}")
    h.set("prodType", parsed.get("prodType") or "UPI")

    t = ET.SubElement(root, _qname("Txn"))
    t.set("id", parsed.get("txnId") or "unknown")
    t.set("type", "CREDIT")

    r = ET.SubElement(root, _qname("Resp"))
    r.set("reqMsgId", req_msg)
    r.set("result", result)
    if err_code:
        r.set("errCode", err_code)
    if bal_amt is not None:
        ref = ET.SubElement(r, _qname("Ref"))
        ref.set("balAmt", f"{bal_amt:.2f}")

    xml_str = ET.tostring(root, encoding="unicode", method="xml")
    return ('<?xml version="1.0" encoding="UTF-8"?>\n' + xml_str).encode("utf-8")


@app.post("/api/reqpay")
def reqpay() -> tuple[dict, int]:
    """
    Receive ReqPay from NPCI with Txn.type=CREDIT. Credit the payee's account, then send
    RespPay (CREDIT) to NPCI. Returns 202.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    
    # Log received XML for debugging
    try:
        logger.info("[bene_bank] /api/reqpay received body (first 500 chars): %s", (request.data or b"")[:500].decode("utf-8", errors="replace"))
    except Exception:
        logger.info("[bene_bank] /api/reqpay received body len=%s", len(request.data or b""))
    
    _ensure_session()
    parsed = _parse_reqpay_credit(request.data)
    if not parsed or (parsed.get("txn_type") or "").upper() != "CREDIT":
        logger.info("[bene_bank] ReqPay ignored (not CREDIT): type=%s", parsed.get("txn_type") if parsed else "?")
        return jsonify(status="accepted"), 202

    logger.info("[bene_bank] Received ReqPay CREDIT from NPCI | Payee=%s | Amount=%s | Payer.code=%s | Payee.code=%s", 
                parsed.get("payee_addr"), parsed.get("amount"), parsed.get("payer_code"), parsed.get("payee_code"))

    result = "SUCCESS"
    err_code = None
    bal_amt = None
    with _session_factory() as session:
        account = get_account_by_vpa(session, parsed["payee_addr"])
        amount = parsed["amount"]
        payee_code = parsed.get("payee_code")
        if payee_code == "1111":
            result = "FAILURE"
            err_code = "Code Blocked for Demo"
        elif payee_code == "1234":
            result = "FAILURE"
            err_code = "trial Block"
        elif not account:
            result = "FAILURE"
            err_code = "PAYEE_NOT_FOUND"
        elif amount < MIN_TRANSACTION_AMOUNT:
            result = "FAILURE"
            err_code = "MIN_AMOUNT_NOT_MET"  # Transaction amount below the mandated 20 ₹ minimum
        else:
            account.balance += amount
            session.commit()
            bal_amt = account.balance

    resppay_bytes = _build_resppay_credit(parsed, result=result, err_code=err_code, bal_amt=bal_amt)
    try:
        r = requests.post(
            f"{NPCI_URL.rstrip('/')}/api/resppay",
            data=resppay_bytes,
            headers={"Content-Type": "application/xml"},
            timeout=10,
        )
        logger.info("[bene_bank] RespPay CREDIT sent to NPCI, response %s", r.status_code)
    except requests.RequestException as e:
        logger.warning("[bene_bank] RespPay CREDIT to NPCI failed: %s", e)

    return jsonify(status="accepted"), 202


# ============================================================================
# Phase 2: AI Agent Integration
# ============================================================================

# Initialize Beneficiary Bank Agent (lazy initialization on first use)
_bene_bank_agent = None

def _get_bene_bank_agent():
    """Get Beneficiary Bank Agent instance (lazy initialization)."""
    global _bene_bank_agent
    if _bene_bank_agent is None:
        try:
            from agents import BeneficiaryBankAgent
            from llm import LLM
            
            # Try to initialize LLM, fallback to basic mode if not available
            try:
                llm = LLM(
                    model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    base_url=os.environ.get("LLM_BASE_URL"),
                )
                logger.info("[Bene Bank Agent] LLM initialized")
            except Exception as e:
                logger.warning(f"[Bene Bank Agent] LLM initialization failed: {e}, using fallback mode")
                llm = None
            
            _bene_bank_agent = BeneficiaryBankAgent(llm_instance=llm)
            logger.info(f"[Bene Bank Agent] Initialized: {_bene_bank_agent.agent_name}")
        except ImportError as e:
            logger.error(f"[Bene Bank Agent] Failed to import agent infrastructure: {e}")
            _bene_bank_agent = None
    return _bene_bank_agent


@app.post("/api/agent/manifest")
def receive_manifest_endpoint():
    """Receive manifest via A2A protocol."""
    agent = _get_bene_bank_agent()
    if not agent:
        return jsonify(error="Beneficiary Bank Agent not available"), 503
    
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
        
        # Receive and acknowledge manifest
        result = agent.receive_manifest(manifest)
        
        # Update orchestrator immediately when manifest is received
        try:
            import requests
            orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:6000")
            # Try localhost fallback
            try:
                requests.post(
                    f"{orchestrator_url}/api/orchestrator/status",
                    json={
                        "change_id": manifest.change_id,
                        "agent_id": agent.agent_id,
                        "status": "RECEIVED",
                        "details": f"Received manifest: '{manifest.description[:100]}'"
                    },
                    timeout=2,
                )
            except:
                requests.post(
                    "http://localhost:8881/api/orchestrator/status",
                    json={
                        "change_id": manifest.change_id,
                        "agent_id": agent.agent_id,
                        "status": "RECEIVED",
                        "details": f"Received manifest: '{manifest.description[:100]}'"
                    },
                    timeout=2,
                )
        except Exception as e:
            logger.warning(f"Failed to update orchestrator: {e}")
        
        # Process manifest synchronously
        try:
            process_result = agent.process_manifest(manifest)
            
            # Update orchestrator with final status
            try:
                import requests
                orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:6000")
                # Ensure process_result has a message field for better logging
                final_message = process_result.get("message", "")
                if not final_message:
                    applied_count = len(process_result.get("applied_changes", []))
                    final_message = f"Processing complete. {applied_count} file(s) updated successfully."
                
                requests.post(
                    f"{orchestrator_url}/api/orchestrator/status",
                    json={
                        "change_id": manifest.change_id,
                        "agent_id": agent.agent_id,
                        "status": process_result.get("status", "RECEIVED"),
                        "details": {"message": final_message, **process_result},
                    },
                    timeout=5,
                )
            except Exception as e:
                logger.warning(f"[Bene Bank Agent] Failed to update orchestrator: {e}")
            
            return jsonify(process_result), 200
        except Exception as e:
            logger.error(f"[Bene Bank Agent] Error processing manifest: {e}")
            return jsonify({**result, "processing_error": str(e)}), 200
        
    except Exception as e:
        logger.error(f"[Bene Bank Agent] Error receiving manifest: {e}")
        return jsonify(error=str(e)), 500


@app.get("/api/agent/status/<change_id>")
def get_agent_status(change_id: str):
    """Get agent status for a specific change."""
    agent = _get_bene_bank_agent()
    if not agent:
        return jsonify(error="Beneficiary Bank Agent not available"), 503
    
    status = agent.get_status(change_id)
    if status:
        return jsonify(status), 200
    return jsonify(error="Change not found"), 404


if __name__ == "__main__":
    _startup()
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)

