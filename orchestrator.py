"""
Orchestrator/Coordinator for tracking change status across all agents.
"""

import logging
import os
import requests  # Added for proxying
import json

from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from flask import Flask, jsonify, request, send_from_directory  # Added send_from_directory

from manifest import ChangeManifest, ChangeType
from agents.base_agent import AgentStatus

from dotenv import load_dotenv

# Load environment variables
load_dotenv()

DATA_FILE = "orchestrator_state.json"



# Filter out noisy polling logs
class EndpointFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return "/api/orchestrator/changes" not in record.getMessage()

# Configure logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] [orchestrator] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    stream=sys.stderr
)
# specific logging for werkzeug
logging.getLogger("werkzeug").addFilter(EndpointFilter())
werkzeug_logger = logging.getLogger('werkzeug')
werkzeug_logger.setLevel(logging.INFO)

logger = logging.getLogger(__name__)

app = Flask(__name__, static_folder='orchestrator/static', static_url_path='/static')


# Request logging middleware (but skip polling endpoints to reduce noise)
@app.before_request
def log_request():
    if "/api/orchestrator/changes" not in request.path:
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
    if "/api/orchestrator/changes" not in request.path:
        logger.info("<== Response %s %s | Status: %s | Content-Type: %s | Content-Length: %s",
                    request.method, request.path,
                    response.status_code,
                    response.content_type or "N/A",
                    response.content_length or 0)
    return response

# In-memory storage for orchestrator state
_change_tracking: Dict[str, Dict[str, Any]] = {}
_agent_statuses: Dict[str, Dict[str, Any]] = {}


class Orchestrator:
    """Orchestrator for tracking change propagation across agents."""
    
    def __init__(self):
        """Initialize orchestrator."""
        self.change_tracking = {}
        self.agent_statuses = {}
        self.load_state()

    def load_state(self):
        """Load state from local file."""
        if os.path.exists(DATA_FILE):
            try:
                with open(DATA_FILE, 'r') as f:
                    data = json.load(f)
                    self.change_tracking = data.get("change_tracking", {})
                    logger.info(f"[Orchestrator] Loaded state from {DATA_FILE} ({len(self.change_tracking)} changes)")
            except Exception as e:
                logger.error(f"[Orchestrator] Failed to load state: {e}")

    def save_state(self):
        """Save state to local file."""
        try:
            with open(DATA_FILE, 'w') as f:
                json.dump({"change_tracking": self.change_tracking}, f, indent=2)
        except Exception as e:
            logger.error(f"[Orchestrator] Failed to save state: {e}")
    
    def register_change(self, manifest: ChangeManifest, receivers: List[str]):
        """
        Register a new change for tracking.
        
        Args:
            manifest: Change manifest
            receivers: List of receiver agent IDs
        """
        change_id = manifest.change_id
        
        # Initialize details structure for all receivers
        details = {}
        for receiver in receivers:
            details[receiver] = {
                "logs": [{
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": AgentStatus.RECEIVED.value,
                    "message": f"Change registered. Waiting for agent to receive manifest..."
                }]
            }
        
        self.change_tracking[change_id] = {
            "manifest": manifest.to_dict(),
            "receivers": receivers,
            "statuses": {receiver: AgentStatus.RECEIVED.value for receiver in receivers},
            "details": details,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        
        logger.info("=" * 80)
        logger.info(f"📝 CHANGE REGISTERED IN ORCHESTRATOR")
        logger.info(f"   Change ID: {change_id[:8]}...")
        logger.info(f"   Receivers: {len(receivers)} agents - {', '.join(receivers)}")
        logger.info("=" * 80)
        self.save_state()
    
    def update_agent_status(
        self,
        change_id: str,
        agent_id: str,
        status: AgentStatus,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        Update status for a specific agent's processing of a change.
        
        Args:
            change_id: Change ID
            agent_id: Agent ID
            status: New status
            details: Optional additional details
        """
        if change_id not in self.change_tracking:
            logger.warning(f"[Orchestrator] Unknown change_id: {change_id}")
            return
        
        self.change_tracking[change_id]["statuses"][agent_id] = status.value
        self.change_tracking[change_id]["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        # Initialize details structure if missing
        if "details" not in self.change_tracking[change_id]:
            self.change_tracking[change_id]["details"] = {}
            
        if agent_id not in self.change_tracking[change_id]["details"]:
            self.change_tracking[change_id]["details"][agent_id] = {"logs": []}
            
        # Append log entry
        # Handle different types of details: string, dict, or None
        log_data = {}
        if isinstance(details, str):
            message = details
        elif isinstance(details, dict):
            # Try to extract meaningful message from dict
            message = details.get("message", "") or details.get("status", "") or details.get("error", "")
            if not message and "applied_changes" in details:
                change_count = len(details.get("applied_changes", []))
                message = f"Processed manifest: {change_count} file(s) updated"
            if not message:
                message = f"Status: {status.value}"
            # Store full details
            log_data = details
        else:
            message = f"Status: {status.value}"
        
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status.value,
            "message": message or f"Status updated to {status.value}",
            "data": log_data  # Store structured data
        }
        
        self.change_tracking[change_id]["details"][agent_id]["logs"].append(log_entry)
        
        logger.info(f"📊 Agent Status Update - {agent_id}: {status.value} (Change: {change_id[:8]}...)")
        self.save_state()
    
    def get_change_status(self, change_id: str) -> Optional[Dict[str, Any]]:
        """
        Get status for a specific change.
        
        Args:
            change_id: Change ID
            
        Returns:
            Status dictionary or None if not found
        """
        return self.change_tracking.get(change_id)
    
    def get_all_changes(self) -> Dict[str, Dict[str, Any]]:
        """Get all tracked changes."""
        return self.change_tracking
    
    def get_summary(self) -> Dict[str, Any]:
        """Get summary of all changes."""
        total = len(self.change_tracking)
        all_ready = sum(
            1
            for change in self.change_tracking.values()
            if all(status == AgentStatus.READY.value for status in change["statuses"].values())
        )
        
        return {
            "total_changes": total,
            "all_ready": all_ready,
            "in_progress": total - all_ready,
        }


# Global orchestrator instance
orchestrator = Orchestrator()


@app.route("/")
def index():
    """Serve the dashboard UI."""
    try:
        return send_from_directory(app.static_folder, 'index.html')
    except Exception as e:
        logger.error(f"Error serving index.html: {e}")
        return f"Error loading page: {str(e)}", 500


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint."""
    return jsonify(status="ok"), 200


@app.route("/api/orchestrator/status", methods=["POST"])
def update_status():
    """Receive status updates from agents."""
    data = request.json
    
    change_id = data.get("change_id")
    agent_id = data.get("agent_id")
    status_str = data.get("status")
    details = data.get("details")
    
    if not all([change_id, agent_id, status_str]):
        return jsonify(error="Missing required fields"), 400
    
    try:
        status = AgentStatus(status_str)
        orchestrator.update_agent_status(change_id, agent_id, status, details)
        return jsonify(status="updated"), 200
    except ValueError:
        return jsonify(error=f"Invalid status: {status_str}"), 400


@app.route("/api/orchestrator/change/<change_id>", methods=["GET"])
def get_change_status(change_id: str):
    """Get status for a specific change."""
    status = orchestrator.get_change_status(change_id)
    if status:
        return jsonify(status), 200
    return jsonify(error="Change not found"), 404


@app.route("/api/orchestrator/changes", methods=["GET"])
def get_all_changes():
    """Get all tracked changes."""
    return jsonify(orchestrator.get_all_changes()), 200


@app.route("/api/orchestrator/summary", methods=["GET"])
def get_summary():
    """Get summary of all changes."""
    return jsonify(orchestrator.get_summary()), 200


@app.route("/api/orchestrator/register", methods=["POST"])
def register_change():
    """Register a new change for tracking."""
    data = request.json
    
    manifest_dict = data.get("manifest")
    receivers = data.get("receivers", [])
    
    if not manifest_dict:
        return jsonify(error="Missing manifest"), 400
    
    manifest = ChangeManifest.from_dict(manifest_dict)
    orchestrator.register_change(manifest, receivers)
    
    return jsonify(status="registered", change_id=manifest.change_id), 200


@app.route("/api/ui/deploy", methods=["POST"])
def deploy_change_proxy():
    """
    Proxy endpoint for the UI to deploy a change.
    Forwards request to NPCI agent which handles creation & dispatch.
    """
    try:
        data = request.json
        receivers = data.get("receivers", [])
        description = data.get("description", "")
        change_type = data.get("change_type", "api_change")
        
        logger.info("=" * 80)
        logger.info("🚀 NEW DEPLOYMENT REQUEST RECEIVED")
        logger.info("=" * 80)
        logger.info(f"📝 Description: {description}")
        logger.info(f"🔧 Change Type: {change_type}")
        logger.info(f"🎯 Target Agents: {', '.join(receivers)}")
        logger.info("=" * 80)
        
        # Detect if running in Docker or locally
        # If NPCI_URL is explicitly set, use it
        npci_url = os.environ.get("NPCI_URL")
        
        if not npci_url:
            # Try to detect environment - check if we can resolve 'npci' hostname
            # If running in Docker, 'npci' hostname will resolve
            # If running locally, use localhost with external port
            try:
                import socket
                socket.gethostbyname('npci')
                # If we can resolve 'npci', we're likely in Docker network
                npci_url = "http://npci:6002"
            except socket.gaierror:
                # Can't resolve 'npci', we're running locally
                # Use external port from docker-compose (5050)
                npci_url = os.environ.get("NPCI_URL_LOCAL", "http://localhost:5050")
        
        logger.info(f"🔌 Connecting to NPCI Agent at: {npci_url}")
        logger.info(f"📤 SENDING REQUEST TO NPCI AGENT")
        logger.info(f"   Prompt: '{description}'")
        
        # Forward request to NPCI
        resp = requests.post(
            f"{npci_url}/api/agent/create-manifest",
            json=data,
            timeout=120  # Increased timeout for LLM processing
        )
        
        if resp.status_code == 200:
            resp_data = resp.json()
            change_id = resp_data.get("change_id") or (resp_data.get("manifest", {}).get("change_id") if resp_data.get("manifest") else None)
            
            if change_id:
                logger.info("=" * 80)
                logger.info(f"✅ CHANGE SUCCESSFULLY CREATED")
                logger.info(f"🆔 Change ID: {change_id}")
                logger.info(f"📨 Dispatching to agents: {', '.join(receivers)}")
                logger.info("=" * 80)
                
                # IMPORTANT: Register the change IMMEDIATELY if not already registered
                # This ensures it appears in the UI right away
                if change_id not in orchestrator.change_tracking:
                    manifest_dict = resp_data.get("manifest", {})
                    if not manifest_dict:
                        # Create a temporary manifest if NPCI didn't return it
                        temp_manifest = ChangeManifest(
                            change_id=change_id,
                            change_type=ChangeType(change_type),
                            description=description,
                            affected_components=data.get("affected_components", []),
                        )
                        orchestrator.register_change(temp_manifest, receivers)
                    else:
                        manifest = ChangeManifest.from_dict(manifest_dict)
                        orchestrator.register_change(manifest, receivers)
                
                # Update NPCI agent status to show it received the prompt
                orchestrator.update_agent_status(
                    change_id,
                    "NPCI_AGENT",
                    AgentStatus.RECEIVED,
                    f"Received prompt: '{description}'"
                )
        
        return (resp.content, resp.status_code, resp.headers.items())
    except Exception as e:
        logger.error(f"[Orchestrator] Proxy error: {e}")
        return jsonify(error=f"Failed to reach NPCI agent: {str(e)}"), 502


if __name__ == "__main__":
    port = int(os.environ.get("ORCHESTRATOR_PORT", 8881))
    logger.info("")
    logger.info("=" * 80)
    logger.info("🎯 UPI AI ORCHESTRATOR STARTING")
    logger.info("=" * 80)
    logger.info(f"🌐 Server Address: 0.0.0.0:{port}")
    logger.info(f"📁 Static Folder: {app.static_folder}")
    logger.info(f"🔗 Static URL Path: {app.static_url_path}")
    logger.info(f"💾 State File: {DATA_FILE}")
    logger.info("=" * 80)
    logger.info("")
    try:
        app.run(host="0.0.0.0", port=port, debug=False)
    except Exception as e:
        logger.error("=" * 80)
        logger.error(f"❌ ORCHESTRATOR FAILED TO START: {e}")
        logger.error("=" * 80)
        raise
