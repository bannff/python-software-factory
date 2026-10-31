from typing import Dict, Optional, Any, Union
from pydantic import BaseModel, Field, field_validator
from datetime import datetime, timezone


class ContextEnvelope(BaseModel):
    """
    Standard envelope for passing context across modules.
    Matching the 'workflow-module' and 'super-agent' pattern.
    """

    tenant_id: Optional[str] = None
    principal_id: Optional[str] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict)

    @field_validator("attributes")
    @classmethod
    def validate_attributes(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure attributes are simple types and bounded size."""
        MAX_ATTRS = 50
        MAX_KEY_LEN = 64
        MAX_VAL_LEN = 1024

        if len(v) > MAX_ATTRS:
            raise ValueError(f"Too many attributes (max {MAX_ATTRS})")

        for k, val in v.items():
            if len(k) > MAX_KEY_LEN:
                raise ValueError(f"Attribute key too long: {k}")
            if isinstance(val, str) and len(val) > MAX_VAL_LEN:
                raise ValueError(f"Attribute value too long for key {k}")

        return v
