from datetime import datetime, timezone
from typing import Dict, Optional, Union
from pydantic import BaseModel, Field


class OperationEnvelope(BaseModel):
    """
    Standard envelope for all operational tool inputs.
    Ensures context propagation across modules.
    """

    tenant_id: Optional[str] = Field(None, description="Multi-tenant isolation ID")
    principal_id: Optional[str] = Field(
        None, description="User or Customer ID initiating the action"
    )
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    agent_id: Optional[str] = None
    tool_name: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    attributes: Dict[str, Union[str, int, float, bool]] = Field(default_factory=dict, max_length=50)
