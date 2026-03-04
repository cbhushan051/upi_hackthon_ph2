"""
Change Manifest system for Phase 2 - AI Agents for Spec Change → Code Update → Deployment.
"""

import json
import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Any


class ChangeType(str, Enum):
    """Types of changes that can be propagated."""
    XSD_UPDATE = "xsd_update"
    API_CHANGE = "api_change"
    BUSINESS_LOGIC = "business_logic"
    VALIDATION_RULE = "validation_rule"
    FIELD_ADDITION = "field_addition"
    FIELD_MODIFICATION = "field_modification"
    FIELD_REMOVAL = "field_removal"


class ChangeManifest:
    """Manifest describing a specification change to be propagated."""
    
    def __init__(
        self,
        change_id: Optional[str] = None,
        change_type: Optional[ChangeType] = None,
        description: Optional[str] = None,
        affected_components: Optional[List[str]] = None,
        xsd_changes: Optional[Dict[str, Any]] = None,
        code_changes: Optional[Dict[str, Any]] = None,
        test_requirements: Optional[List[str]] = None,
        created_by: str = "NPCI_AGENT",
        timestamp: Optional[str] = None,
    ):
        self.change_id = change_id or str(uuid.uuid4())
        self.change_type = change_type or ChangeType.API_CHANGE
        self.description = description or ""
        self.affected_components = affected_components or []
        self.xsd_changes = xsd_changes or {}
        self.code_changes = code_changes or {}
        self.test_requirements = test_requirements or []
        self.created_by = created_by
        self.timestamp = timestamp or datetime.now(timezone.utc).isoformat()
        self.status = "PENDING"  # PENDING, DISPATCHED, COMPLETED
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert manifest to dictionary."""
        return {
            "change_id": self.change_id,
            "change_type": self.change_type.value if isinstance(self.change_type, ChangeType) else self.change_type,
            "description": self.description,
            "affected_components": self.affected_components,
            "xsd_changes": self.xsd_changes,
            "code_changes": self.code_changes,
            "test_requirements": self.test_requirements,
            "created_by": self.created_by,
            "timestamp": self.timestamp,
            "status": self.status,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ChangeManifest":
        """Create manifest from dictionary."""
        manifest = cls(
            change_id=data.get("change_id"),
            change_type=ChangeType(data.get("change_type", "api_change")),
            description=data.get("description"),
            affected_components=data.get("affected_components", []),
            xsd_changes=data.get("xsd_changes", {}),
            code_changes=data.get("code_changes", {}),
            test_requirements=data.get("test_requirements", []),
            created_by=data.get("created_by", "NPCI_AGENT"),
            timestamp=data.get("timestamp"),
        )
        manifest.status = data.get("status", "PENDING")
        return manifest
    
    def to_json(self) -> str:
        """Serialize manifest to JSON."""
        return json.dumps(self.to_dict(), indent=2)
    
    @classmethod
    def from_json(cls, json_str: str) -> "ChangeManifest":
        """Deserialize manifest from JSON."""
        return cls.from_dict(json.loads(json_str))
