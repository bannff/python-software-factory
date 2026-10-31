"""Strict MCP contracts for the tokenless credentialed-egress tool."""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, JsonValue

from ...runtime.egress_models import EgressRequest

JsonObject = dict[str, JsonValue]


class CredentialedEgressInput(BaseModel):
    """The ``request`` object is the binding-matched egress coordinate + payload."""
    model_config = ConfigDict(extra="forbid", strict=True)
    request: EgressRequest


class CredentialedEgressOutput(BaseModel):
    """Sanitized business result — never a token, secret, or provider header."""
    model_config = ConfigDict(extra="forbid", strict=True)
    status: Literal["ok", "unauthorized", "denied"]
    result: JsonObject = {}


__all__ = ["CredentialedEgressInput", "CredentialedEgressOutput"]
