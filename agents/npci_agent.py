"""
NPCI Switch AI Agent - Creates change manifests and dispatches them.
"""

import logging
from typing import Dict, List, Optional, Any

from llm import LLM
from manifest import ChangeManifest, ChangeType
from a2a_protocol import A2AClient, A2AMessage
from .base_agent import BaseAgent, AgentStatus

logger = logging.getLogger(__name__)


class NPCIAgent(BaseAgent):
    """NPCI Switch agent that creates and dispatches change manifests."""
    
    def __init__(self, llm_instance: Optional[LLM] = None):
        """Initialize NPCI agent."""
        super().__init__(
            agent_id="NPCI_AGENT",
            agent_name="NPCI Switch Agent",
            llm_instance=llm_instance,
        )
        self.a2a_client = A2AClient()
    
    def create_manifest(
        self,
        description: str,
        change_type: ChangeType,
        affected_components: List[str],
        xsd_changes: Optional[Dict] = None,
        code_changes: Optional[Dict] = None,
        test_requirements: Optional[List[str]] = None,
    ) -> ChangeManifest:
        """
        Create a new change manifest.
        
        Args:
            description: Description of the change
            change_type: Type of change
            affected_components: List of component names affected
            xsd_changes: Optional XSD change details
            code_changes: Optional code change details
            test_requirements: Optional test requirements
            
        Returns:
            Created manifest
        """
        manifest = ChangeManifest(
            change_type=change_type,
            description=description,
            affected_components=affected_components,
            xsd_changes=xsd_changes or {},
            code_changes=code_changes or {},
            test_requirements=test_requirements or [],
            created_by=self.agent_id,
        )
        
        
        logger.info(f"[{self.agent_name}] Created manifest: {manifest.change_id}")
        
        # Determine orchestrator URL
        from a2a_protocol import A2AClient
        a2a = A2AClient()
        # Hacky: send initial status to orchestrator manually since NPCI doesn't "receive" its own manifest in the same way
        # In a real system, we'd have a cleaner way, but for now we use A2A client to update orchestrator
        try:
            import requests
            orchestrator_url = a2a.get_service_url("ORCHESTRATOR")
            
            # Register change first
            requests.post(
                f"{orchestrator_url}/api/orchestrator/register",
                json={"manifest": manifest.to_dict(), "receivers": []},
                timeout=5
            )

            # Then send status
            requests.post(
                f"{orchestrator_url}/api/orchestrator/status",
                json={
                    "change_id": manifest.change_id,
                    "agent_id": self.agent_id,
                    "status": "RECEIVED",  # Initial status
                    "details": f"Manifest created: {manifest.description}"
                },
                timeout=5
            )
        except Exception:
            pass # Ignore errors here, just best effort logging
            
        return manifest
    
    def dispatch_manifest(
        self,
        manifest: ChangeManifest,
        receivers: Optional[List[str]] = None,
    ) -> Dict[str, bool]:
        """
        Dispatch manifest to receiver agents.
        
        Args:
            manifest: Manifest to dispatch
            receivers: List of receiver agent IDs (defaults to all bank/PSP agents)
            
        Returns:
            Dictionary mapping receiver to success status
        """
        if receivers is None:
            receivers = [
                "REMITTER_BANK_AGENT",
                "BENEFICIARY_BANK_AGENT",
                "PAYER_PSP_AGENT",
                "PAYEE_PSP_AGENT",
            ]
        
        manifest.status = "DISPATCHED"
        results = self.a2a_client.broadcast_manifest(
            manifest_dict=manifest.to_dict(),
            sender=self.agent_id,
            receivers=receivers,
        )
        
        logger.info(f"[{self.agent_name}] Dispatched manifest {manifest.change_id} to {len(receivers)} agents")
        
        # Log dispatch
        try:
            import requests
            orchestrator_url = self.a2a_client.get_service_url("ORCHESTRATOR")
            requests.post(
                f"{orchestrator_url}/api/orchestrator/status",
                json={
                    "change_id": manifest.change_id,
                    "agent_id": self.agent_id,
                    "status": "DISPATCHED", 
                    "details": {
                        "message": f"Dispatched to {len(receivers)} agents: {', '.join(receivers)}",
                        "receivers": receivers,
                        "manifest": manifest.to_dict()
                    }
                },
                timeout=5
            )
        except Exception:
            pass
        
        return results
    
    def process_manifest(self, manifest: ChangeManifest) -> Dict[str, Any]:
        """NPCI agent doesn't process manifests, it creates them."""
        return {
            "agent_id": self.agent_id,
            "status": "NPCI agent creates manifests, does not process them",
        }
    
    def get_component_paths(self) -> List[str]:
        """Get NPCI component file paths."""
        return [
            "npci/app.py",
            "common/schemas/upi_pay_request.xsd",
            "common/schemas/upi_resppay_response.xsd",
        ]
