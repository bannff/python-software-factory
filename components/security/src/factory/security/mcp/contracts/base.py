"""Shared strict DTO base for Security FastMCP boundaries."""
from __future__ import annotations
from typing import Any
from pydantic import BaseModel, ConfigDict

class DTO(BaseModel):
    """Strict same-brick transport contract base."""
    model_config = ConfigDict(extra="forbid", strict=True)

class EmptyInput(DTO):
    pass

class DynamicOutput(DTO):
    """Concrete escape hatch for domain payloads whose contents are dynamic."""
    payload: dict[str, Any]
