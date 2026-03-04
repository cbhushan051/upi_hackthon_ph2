"""
Agent-to-Agent (A2A) communication protocol for Phase 2.
"""

import json
import logging
from typing import Dict, Optional, Any
import requests

logger = logging.getLogger(__name__)


class A2AMessage:
    """Message structure for Agent-to-Agent communication."""
    
    def __init__(
        self,
        message_type: str,
        sender: str,
        receiver: str,
        payload: Dict[str, Any],
        message_id: Optional[str] = None,
        correlation_id: Optional[str] = None,
    ):
        self.message_type = message_type  # MANIFEST, STATUS_UPDATE, ACK, ERROR
        self.sender = sender
        self.receiver = receiver
        self.payload = payload
        self.message_id = message_id
        self.correlation_id = correlation_id
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return {
            "message_type": self.message_type,
            "sender": self.sender,
            "receiver": self.receiver,
            "payload": self.payload,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AMessage":
        """Create message from dictionary."""
        return cls(
            message_type=data.get("message_type"),
            sender=data.get("sender"),
            receiver=data.get("receiver"),
            payload=data.get("payload", {}),
            message_id=data.get("message_id"),
            correlation_id=data.get("correlation_id"),
        )


class A2AClient:
    """Client for sending A2A messages."""
    
    # Agent endpoint mappings
    AGENT_ENDPOINTS = {
        "NPCI_AGENT": "/api/agent/manifest",
        "REMITTER_BANK_AGENT": "/api/agent/manifest",
        "BENEFICIARY_BANK_AGENT": "/api/agent/manifest",
        "PAYER_PSP_AGENT": "/api/agent/manifest",
        "PAYEE_PSP_AGENT": "/api/agent/manifest",
        "ORCHESTRATOR": "/api/orchestrator/status",
    }
    
    # Base URLs for each agent service (Docker mode)
    SERVICE_URLS_DOCKER = {
        "NPCI_AGENT": "http://npci:6002",
        "REMITTER_BANK_AGENT": "http://rem_bank:6005",
        "BENEFICIARY_BANK_AGENT": "http://bene_bank:6001",
        "PAYER_PSP_AGENT": "http://payer_psp:6004",
        "PAYEE_PSP_AGENT": "http://payee_psp:6003",
        "ORCHESTRATOR": "http://orchestrator:6000",
    }
    
    # Base URLs for local execution mode (pointing to Docker exposed ports)
    SERVICE_URLS_LOCAL = {
        "NPCI_AGENT": "http://localhost:5050",
        "REMITTER_BANK_AGENT": "http://localhost:5080",
        "BENEFICIARY_BANK_AGENT": "http://localhost:5090",
        "PAYER_PSP_AGENT": "http://localhost:5060",
        "PAYEE_PSP_AGENT": "http://localhost:5070",
        "ORCHESTRATOR": "http://localhost:8081",
    }
    
    @classmethod
    def get_service_url(cls, receiver: str) -> Optional[str]:
        """
        Get the base URL for a receiver agent, prioritizing environment variables.
        
        Args:
            receiver: Agent ID or service name
            
        Returns:
            Base URL or None if not found
        """
        import os
        
        # 1. Check for direct environment variable match (e.g. REMITTER_BANK_AGENT_URL)
        env_url = os.environ.get(f"{receiver}_URL")
        if env_url:
            return env_url
            
        # 2. Check for common shorthand environment variables
        shorthand_map = {
            "REMITTER_BANK_AGENT": "REM_BANK_URL",
            "BENEFICIARY_BANK_AGENT": "BENE_BANK_URL",
            "NPCI_AGENT": "NPCI_URL",
            "PAYER_PSP_AGENT": "PAYER_PSP_URL",
            "PAYEE_PSP_AGENT": "PAYEE_PSP_URL",
            "ORCHESTRATOR": "ORCHESTRATOR_URL"
        }
        shorthand_env = shorthand_map.get(receiver)
        if shorthand_env:
            env_url = os.environ.get(shorthand_env)
            if env_url:
                return env_url

        # 3. Fallback to hardcoded defaults
        service_urls = cls.SERVICE_URLS_LOCAL if os.environ.get("A2A_LOCAL_MODE", "false").lower() == "true" else cls.SERVICE_URLS_DOCKER
        return service_urls.get(receiver)
    
    @classmethod
    def send_message(
        cls,
        message: A2AMessage,
        timeout: int = 30,
    ) -> Optional[Dict[str, Any]]:
        """
        Send an A2A message to the target agent.
        
        Args:
            message: A2A message to send
            timeout: Request timeout in seconds
            
        Returns:
            Response dictionary or None if failed
        """
        receiver = message.receiver
        endpoint = cls.AGENT_ENDPOINTS.get(receiver, "/api/agent/manifest")
        base_url = cls.get_service_url(receiver)
        
        if not base_url:
            logger.error(f"Unknown receiver: {receiver}")
            return None
        
        url = f"{base_url.rstrip('/')}{endpoint}"
        
        try:
            response = requests.post(
                url,
                json=message.to_dict(),
                headers={"Content-Type": "application/json"},
                timeout=timeout,
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            # In local mode, these failures are expected - use debug level instead of error
            import os
            is_local = os.environ.get("A2A_LOCAL_MODE", "false").lower() == "true"
            log_level = logger.debug if is_local else logger.error
            log_level(f"Failed to send A2A message to {receiver} at {url}: {e}")
            return None
    
    @classmethod
    def broadcast_manifest(
        cls,
        manifest_dict: Dict[str, Any],
        sender: str,
        receivers: list[str],
    ) -> Dict[str, bool]:
        """
        Broadcast a manifest to multiple agents.
        
        Args:
            manifest_dict: Manifest as dictionary
            sender: Sender agent ID
            receivers: List of receiver agent IDs
            
        Returns:
            Dictionary mapping receiver to success status
        """
        results = {}
        for receiver in receivers:
            message = A2AMessage(
                message_type="MANIFEST",
                sender=sender,
                receiver=receiver,
                payload={"manifest": manifest_dict},
            )
            result = cls.send_message(message)
            results[receiver] = result is not None
        return results
