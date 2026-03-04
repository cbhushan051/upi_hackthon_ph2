"""
Flask API endpoints for agent integration with existing services.
"""

import logging
import os
from flask import Flask, jsonify, request

from manifest import ChangeManifest
from agents import NPCIAgent, RemitterBankAgent, BeneficiaryBankAgent
from agents.base_agent import AgentStatus
from llm import LLM

logger = logging.getLogger(__name__)

app = Flask(__name__)

# Initialize agents (singleton instances)
_npci_agent: NPCIAgent | None = None
_remitter_agent: RemitterBankAgent | None = None
_beneficiary_agent: BeneficiaryBankAgent | None = None


def get_npci_agent() -> NPCIAgent:
    """Get or create NPCI agent instance."""
    global _npci_agent
    if _npci_agent is None:
        try:
            llm = LLM(
                model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("LLM_BASE_URL"),
            )
        except Exception:
            # Fallback mode if LLM initialization fails
            llm = LLM(api_key="")
        _npci_agent = NPCIAgent(llm_instance=llm)
    return _npci_agent


def get_remitter_agent() -> RemitterBankAgent:
    """Get or create Remitter Bank agent instance."""
    global _remitter_agent
    if _remitter_agent is None:
        try:
            llm = LLM(
                model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("LLM_BASE_URL"),
            )
        except Exception:
            # Fallback mode if LLM initialization fails
            llm = LLM(api_key="")
        _remitter_agent = RemitterBankAgent(llm_instance=llm)
    return _remitter_agent


def get_beneficiary_agent() -> BeneficiaryBankAgent:
    """Get or create Beneficiary Bank agent instance."""
    global _beneficiary_agent
    if _beneficiary_agent is None:
        try:
            llm = LLM(
                model=os.environ.get("LLM_MODEL", "gpt-3.5-turbo"),
                api_key=os.environ.get("OPENAI_API_KEY"),
                base_url=os.environ.get("LLM_BASE_URL"),
            )
        except Exception:
            # Fallback mode if LLM initialization fails
            llm = LLM(api_key="")
        _beneficiary_agent = BeneficiaryBankAgent(llm_instance=llm)
    return _beneficiary_agent


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(status="ok"), 200


@app.route("/api/agent/manifest", methods=["POST"])
def receive_manifest():
    """
    Receive a manifest from another agent (A2A protocol).
    """
    data = request.json
    
    if not data or "payload" not in data:
        return jsonify(error="Invalid message format"), 400
    
    payload = data.get("payload", {})
    manifest_dict = payload.get("manifest")
    
    if not manifest_dict:
        return jsonify(error="Missing manifest in payload"), 400
    
    try:
        manifest = ChangeManifest.from_dict(manifest_dict)
        sender = data.get("sender", "UNKNOWN")
        
        logger.info(f"Received manifest {manifest.change_id} from {sender}")
        
        # Determine which agent should process this based on service
        # This would be determined by the service that receives the request
        # For now, we'll check a header or environment variable
        agent_type = request.headers.get("X-Agent-Type") or os.environ.get("AGENT_TYPE", "REMITTER_BANK_AGENT")
        
        if agent_type == "NPCI_AGENT":
            agent = get_npci_agent()
        elif agent_type == "REMITTER_BANK_AGENT":
            agent = get_remitter_agent()
        elif agent_type == "BENEFICIARY_BANK_AGENT":
            agent = get_beneficiary_agent()
        else:
            return jsonify(error=f"Unknown agent type: {agent_type}"), 400
        
        # Receive and process manifest
        ack = agent.receive_manifest(manifest)
        
        # Process manifest asynchronously (in production, use a task queue)
        try:
            result = agent.process_manifest(manifest)
            ack.update(result)
        except Exception as e:
            logger.error(f"Error processing manifest: {e}")
            ack["error"] = str(e)
        
        return jsonify(ack), 200
        
    except Exception as e:
        logger.error(f"Error handling manifest: {e}")
        return jsonify(error=str(e)), 500


@app.route("/api/agent/status/<change_id>", methods=["GET"])
def get_agent_status(change_id: str):
    """Get status for a specific change from an agent."""
    agent_type = request.headers.get("X-Agent-Type") or os.environ.get("AGENT_TYPE", "REMITTER_BANK_AGENT")
    
    if agent_type == "NPCI_AGENT":
        agent = get_npci_agent()
    elif agent_type == "REMITTER_BANK_AGENT":
        agent = get_remitter_agent()
    elif agent_type == "BENEFICIARY_BANK_AGENT":
        agent = get_beneficiary_agent()
    else:
        return jsonify(error=f"Unknown agent type: {agent_type}"), 400
    
    status = agent.get_status(change_id)
    return jsonify(status), 200


@app.route("/api/agent/create-manifest", methods=["POST"])
def create_manifest():
    """
    Create a new manifest (NPCI agent only).
    """
    data = request.json
    
    if not data:
        return jsonify(error="Missing request body"), 400
    
    try:
        agent = get_npci_agent()
        
        from manifest import ChangeType
        
        manifest = agent.create_manifest(
            description=data.get("description", ""),
            change_type=ChangeType(data.get("change_type", "api_change")),
            affected_components=data.get("affected_components", []),
            xsd_changes=data.get("xsd_changes"),
            code_changes=data.get("code_changes"),
            test_requirements=data.get("test_requirements"),
        )
        
        # Optionally dispatch immediately
        if data.get("dispatch", False):
            receivers = data.get("receivers")
            results = agent.dispatch_manifest(manifest, receivers)
            return jsonify({
                "manifest": manifest.to_dict(),
                "dispatch_results": results,
            }), 200
        
        return jsonify({"manifest": manifest.to_dict()}), 200
        
    except Exception as e:
        logger.error(f"Error creating manifest: {e}")
        return jsonify(error=str(e)), 500


if __name__ == "__main__":
    port = int(os.environ.get("AGENT_API_PORT", 7000))
    logger.info(f"[Agent API] Starting on 0.0.0.0:{port}")
    app.run(host="0.0.0.0", port=port, debug=True)
