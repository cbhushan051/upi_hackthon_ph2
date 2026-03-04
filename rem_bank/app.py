import logging
import os
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

import requests
from flask import Flask, jsonify, request

from db import get_account_by_vpa, init_db, seed_sample_accounts

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [rem_bank] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    stream=sys.stderr,
    force=True,
)
logger = logging.getLogger(__name__)

# Set Flask's werkzeug logger to INFO to see all HTTP requests
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)

# Minimum transaction amount (in rupees) enforced for all debit transactions
MIN_TXN_AMOUNT = 20
# Maximum transaction amount (in rupees) enforced for all debit transactions
MAX_TXN_AMOUNT = 20000
# Supported UPI purpose codes. Extend as needed.
PURPOSE_CODES = {
    "44": "Utility Payments",  # Added per change manifest
}
app = Flask(__name__)
NS = "http://npci.org/upi/schema/"
NPCI_URL = os.environ.get("NPCI_URL", "http://npci:5000")
_session_factory = None


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


def _qname(tag: str) -> str:
    return f"{{{NS}}}{tag}"


def _startup() -> None:
    global _session_factory
    _session_factory = init_db()
    with _session_factory() as session:
        seed_sample_accounts(session)


def _ensure_session():
    global _session_factory
    if _session_factory is None:
        _startup()


def _parse_reqpay(body: bytes) -> dict | None:
    """Extract Head.msgId, Head.ver, Head.orgId, Head.prodType, Txn.id, Txn.type, Payer.addr, Payer/Amount.value, Payer.code, and optional Purpose.code (e.g., 44 for utility payments)."""
    out = {}
    try:
        root = ET.fromstring(body)
        q = lambda n: f".//{{{NS}}}{n}"
        h = root.find(q("Head"))
        t = root.find(q("Txn"))
        p = root.find(q("Payer"))
        if h is not None:
            out["msgId"] = (h.get("msgId") or "").strip()
            out["ver"] = (h.get("ver") or "2.0").strip()
            out["orgId"] = (h.get("orgId") or "").strip()
            out["prodType"] = (h.get("prodType") or "UPI").strip()
        if t is not None:
            out["txnId"] = (t.get("id") or "").strip()
            out["txnType"] = (t.get("type") or "DEBIT").strip()
            # Optional Purpose element under Txn
            purpose_elem = t.find(q("Purpose"))
            if purpose_elem is not None:
                out["purposeCode"] = (purpose_elem.get("code") or "").strip()
            # Also check for purpose attribute on Txn (per XSD schema)
            txn_purpose = (t.get("purpose") or "").strip()
            if txn_purpose:
                out["txnPurpose"] = txn_purpose
            # Validate purpose code if present
            if "purposeCode" in out and out["purposeCode"] and out["purposeCode"] not in PURPOSE_CODES:
                # Unknown or unsupported purpose code – reject the transaction
                return None
        if p is not None:
            out["payerAddr"] = (p.get("addr") or "").strip()
            # Extract Payer.code attribute
            out["payerCode"] = (p.get("code") or "").strip()
            out["payerType"] = (p.get("type") or "").strip()
            out["payerSeqNum"] = (p.get("seqNum") or "").strip()
            out["payerName"] = (p.get("name") or "").strip()
            amt = p.find(q("Amount"))
            if amt is not None:
                out["amount"] = float(amt.get("value") or 0)
            else:
                out["amount"] = 0.0
                # Validation: Minimum transaction amount of INR 1 (per manifest 155d7935-4535-4561-9fc2-d434d4abbec9)
                if out.get('amount', 0) < 1.0:
                    return None  # Reject transactions below minimum amount
            # Log the extracted Payer.code for debugging
            logger.info("[rem_bank] Parsed Payer.code=%s, Payer.type=%s, Payer.seqNum=%s",
                        out.get("payerCode"), out.get("payerType"), out.get("payerSeqNum"))
            # Validation: Minimum transaction amount enforced (currently MIN_TXN_AMOUNT)
            if out["amount"] < MIN_TXN_AMOUNT:
                return None  # Reject transactions below minimum amount
            # Validation: Maximum transaction amount enforced (currently MAX_TXN_AMOUNT)
            if out["amount"] > MAX_TXN_AMOUNT:
                return None  # Reject transactions above maximum amount
            return out if out.get("payerAddr") and out.get("msgId") else None
    except (ET.ParseError, ValueError, TypeError):
        return None


def _build_resppay_debit(parsed: dict, result: str, err_code: str | None = None, bal_amt: float | None = None) -> bytes:
    """Build RespPay (type=DEBIT) per common/schemas/upi_resppay_response.xsd."""
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    req_msg = parsed.get("msgId") or "req"
    root = ET.Element(_qname("RespPay"))

    h = ET.SubElement(root, _qname("Head"))
    h.set("ver", parsed.get("ver") or "2.0")
    h.set("ts", ts)
    h.set("orgId", "REM_BANK")
    h.set("msgId", f"resppay-debit-{req_msg}")
    h.set("prodType", parsed.get("prodType") or "UPI")

    t = ET.SubElement(root, _qname("Txn"))
    t.set("id", parsed.get("txnId") or "unknown")
    t.set("type", "DEBIT")

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


@app.get("/health")
def health() -> tuple[dict, int]:
    return jsonify(status="ok"), 200


@app.post("/api/reqpay")
def reqpay() -> tuple[dict, int]:
    """
    Receive ReqPay from NPCI with Txn.type=DEBIT. Debit payer's account, then send
    RespPay (DEBIT) to NPCI. Returns 202.
    """
    if not request.data:
        return jsonify(error="Missing body"), 400
    
    # Log received XML for debugging
    try:
        logger.info("[rem_bank] /api/reqpay received body (first 500 chars): %s", (request.data or b"")[:500].decode("utf-8", errors="replace"))
    except Exception:
        logger.info("[rem_bank] /api/reqpay received body len=%s", len(request.data or b""))
    
    _ensure_session()
    parsed = _parse_reqpay(request.data)
    if not parsed:
        return jsonify(error="Invalid ReqPay: could not parse Payer.addr and Amount"), 400

    logger.info(
        "[rem_bank] Received ReqPay DEBIT from NPCI | Payer=%s | Amount=%s | Txn.id=%s",
        parsed.get("payerAddr"),
        parsed.get("amount"),
        parsed.get("txnId"),
    )
    # Block payments for payees with code 1111 (demo rule)
    if parsed.get("payerCode") == "1111":
        return jsonify(error="Code Blocked for Demo", status="rejected"), 400

    result = "SUCCESS"
    err_code = None
    bal_amt = None
    with _session_factory() as session:
        account = get_account_by_vpa(session, parsed["payerAddr"])
        amount = parsed["amount"]
        # Debug: account and amount (use logger so it shows in: docker compose logs -f rem_bank)
        logger.info(
            "[rem_bank] DEBUG account=%s balance=%s amount=%s",
            account.id if account else None,
            getattr(account, "balance", None),
            amount,
        )
        if not account:
            result = "FAILURE"
            err_code = "PAYER_NOT_FOUND"
        elif amount < MIN_TXN_AMOUNT:
            result = "FAILURE"
            err_code = "MIN_AMOUNT_VIOLATION"
        elif amount > MAX_TXN_AMOUNT:
            result = "FAILURE"
            err_code = "MAX_AMOUNT_VIOLATION"
        elif account.balance < amount:
            result = "FAILURE"
            err_code = "INSUFFICIENT_BALANCE"
        else:
            account.balance -= amount
            session.flush()  # ensure UPDATE is sent before commit
            session.commit()
            bal_amt = account.balance

    if result != "SUCCESS":
        return jsonify(error=err_code, status="rejected"), 400

    resppay_bytes = _build_resppay_debit(parsed, result=result, err_code=err_code, bal_amt=bal_amt)
    try:
        requests.post(
            f"{NPCI_URL.rstrip('/')}/api/resppay",
            data=resppay_bytes,
            headers={"Content-Type": "application/xml"},
            timeout=10,
        )
    except requests.RequestException:
        pass  # best-effort; return 202 to NPCI for successful initiation

    return jsonify(status="accepted"), 202


# ============================================================================
# Phase 2: AI Agent Integration
# ============================================================================

# Initialize Remitter Bank Agent (lazy initialization on first use)
_rem_bank_agent = None

def _get_rem_bank_agent():
    """Get Remitter Bank Agent instance (lazy initialization)."""
    global _rem_bank_agent
    if _rem_bank_agent is None:
        try:
            from agents import RemitterBankAgent
            from llm import LLM
            
            # Try to initialize LLM, fallback to basic mode if not available
            try:
                llm = LLM(
                    model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                    api_key=os.environ.get("OPENAI_API_KEY"),
                    base_url=os.environ.get("LLM_BASE_URL"),
                )
                logger.info("[Rem Bank Agent] LLM initialized")
            except Exception as e:
                logger.warning(f"[Rem Bank Agent] LLM initialization failed: {e}, using fallback mode")
                llm = None
            
            _rem_bank_agent = RemitterBankAgent(llm_instance=llm)
            logger.info(f"[Rem Bank Agent] Initialized: {_rem_bank_agent.agent_name}")
        except ImportError as e:
            logger.error(f"[Rem Bank Agent] Failed to import agent infrastructure: {e}")
            _rem_bank_agent = None
    return _rem_bank_agent


@app.post("/api/agent/manifest")
def receive_manifest_endpoint():
    """Receive manifest via A2A protocol."""
    agent = _get_rem_bank_agent()
    if not agent:
        return jsonify(error="Remitter Bank Agent not available"), 503
    
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
            import requests as req
            orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:6000")
            # Try localhost fallback
            try:
                req.post(
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
                req.post(
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
        
        # Process manifest asynchronously in background if needed
        # For now, process synchronously
        try:
            process_result = agent.process_manifest(manifest)
            
            # Update orchestrator with final status
            try:
                import requests as req

                orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:6000")
                # Ensure process_result has a message field for better logging
                final_message = process_result.get("message", "")
                if not final_message:
                    applied_count = len(process_result.get("applied_changes", []))
                    final_message = f"Processing complete. {applied_count} file(s) updated successfully."
                
                req.post(
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
                logger.warning(f"[Rem Bank Agent] Failed to update orchestrator: {e}")
            
            return jsonify(process_result), 200
        except Exception as e:
            logger.error(f"[Rem Bank Agent] Error processing manifest: {e}")
            return jsonify({**result, "processing_error": str(e)}), 200
        
    except Exception as e:
        logger.error(f"[Rem Bank Agent] Error receiving manifest: {e}")
        return jsonify(error=str(e)), 500


@app.get("/api/agent/status/<change_id>")
def get_agent_status(change_id: str):
    """Get agent status for a specific change."""
    agent = _get_rem_bank_agent()
    if not agent:
        return jsonify(error="Remitter Bank Agent not available"), 503
    
    status = agent.get_status(change_id)
    if status:
        return jsonify(status), 200
    return jsonify(error="Change not found"), 404


if __name__ == "__main__":
    _startup()
    port = int(os.environ.get("PORT", 5000))
    logger.info("[rem_bank] Starting on 0.0.0.0:%s (logs go to stderr -> docker compose logs)", port)
    app.run(host="0.0.0.0", port=port)


