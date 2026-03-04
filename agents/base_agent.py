"""
Base agent class for Phase 2 AI agents.
"""

import logging
import os
import requests
from abc import ABC, abstractmethod
from enum import Enum
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timezone

from llm import LLM
from manifest import ChangeManifest

logger = logging.getLogger(__name__)


class AgentStatus(str, Enum):
    """Agent status enumeration."""
    RECEIVED = "RECEIVED"
    APPLIED = "APPLIED"
    TESTED = "TESTED"
    READY = "READY"
    ERROR = "ERROR"


class BaseAgent(ABC):
    """Base class for all AI agents."""
    
    def __init__(
        self,
        agent_id: str,
        agent_name: str,
        llm_instance: Optional[LLM] = None,
    ):
        """
        Initialize base agent.
        
        Args:
            agent_id: Unique identifier for the agent
            agent_name: Human-readable name
            llm_instance: Optional LLM instance
        """
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.llm = llm_instance
        self.status = AgentStatus.RECEIVED
        self.pending_manifests: List[ChangeManifest] = []
        self.completed_manifests: List[str] = []
        self.status_history: List[Dict[str, Any]] = []
    
    @abstractmethod
    def process_manifest(self, manifest: ChangeManifest) -> Dict[str, Any]:
        """
        Process a change manifest.
        
        Args:
            manifest: Change manifest to process
            
        Returns:
            Dictionary with processing results
        """
        pass
    
    @abstractmethod
    def get_component_paths(self) -> List[str]:
        """
        Get list of file paths for this agent's components.
        
        Returns:
            List of file paths
        """
        pass
    
    def receive_manifest(self, manifest: ChangeManifest) -> Dict[str, Any]:
        """
        Receive and acknowledge a manifest.
        
        Args:
            manifest: Change manifest received
            
        Returns:
            Acknowledgment dictionary
        """
        self.pending_manifests.append(manifest)
        self.status = AgentStatus.RECEIVED
        
        self.status_history.append({
            "change_id": manifest.change_id,
            "status": self.status.value,
            "timestamp": manifest.timestamp,
        })
        
        logger.info(f"[{self.agent_name}] Received manifest: {manifest.change_id}")
        
        return {
            "agent_id": self.agent_id,
            "change_id": manifest.change_id,
            "status": self.status.value,
            "message": f"Manifest {manifest.change_id} received",
        }
    
    def update_status(self, change_id: str, status: AgentStatus, message: Union[str, Dict[str, Any]] = ""):
        """
        Update status for a specific change.
        
        Args:
           change_id: ID of the change
           status: New status enum
           message: Log message string OR dictionary with details
        """
        self.status = status
        
        # Extract string message for local logging/history
        log_message = message
        if isinstance(message, dict):
            log_message = message.get("message", str(message))
            
        self.status_history.append({
            "change_id": change_id,
            "status": status.value,
            "message": log_message,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        logger.info(f"[{self.agent_name}] Status update for {change_id}: {status.value} - {log_message}")
        
        # Push update to Orchestrator
        try:
            # Default to Docker network URL
            orchestrator_url = os.environ.get("ORCHESTRATOR_URL", "http://orchestrator:6000")
            
            payload = {
                "change_id": change_id,
                "agent_id": self.agent_id,
                "status": status.value,
                "details": message  # Send full structure (str or dict)
            }
            
            requests.post(
                f"{orchestrator_url}/api/orchestrator/status",
                json=payload,
                timeout=2
            )
        except Exception as e:
            # Don't fail the agent if orchestrator is unreachable, just log it
            logger.warning(f"[{self.agent_name}] Failed to push status to orchestrator: {e}")

    def get_status(self, change_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get current status.
        
        Args:
            change_id: Optional change ID to filter by
            
        Returns:
            Status dictionary
        """
        if change_id:
            history = [h for h in self.status_history if h.get("change_id") == change_id]
            if history:
                return history[-1]
            return {}
        
        return {
            "agent_id": self.agent_id,
            "agent_name": self.agent_name,
            "current_status": self.status.value,
            "pending_count": len(self.pending_manifests),
            "completed_count": len(self.completed_manifests),
        }
