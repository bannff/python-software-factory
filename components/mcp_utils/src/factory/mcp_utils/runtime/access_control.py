"""Immutable transport-neutral authorization contracts."""
from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel, ConfigDict, Field


class FrozenContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class AccessPrincipal(FrozenContract):
    subject: str = Field(min_length=1, max_length=256)
    tenant_id: str | None = Field(default=None, max_length=128)
    client_id: str = Field(min_length=1, max_length=256)
    scopes: tuple[str, ...] = ()
    roles: tuple[str, ...] = ()
    expires_at: int | None = None
    claims: dict[str, Any] = Field(default_factory=dict)


class AccessOperation(FrozenContract):
    action: Literal["discover", "execute"]
    public_name: str = Field(min_length=1, max_length=256)
    brick: str = Field(min_length=1, max_length=128)
    source_name: str = Field(min_length=1, max_length=256)
    category: str | None = Field(default=None, max_length=64)


class AccessDecision(FrozenContract):
    allowed: bool
    reason: str = Field(min_length=1, max_length=128)
    policy_id: str | None = Field(default=None, max_length=128)
    rule_id: str | None = Field(default=None, max_length=128)


class AccessControllerPort(Protocol):
    def principal(self) -> AccessPrincipal | None: ...
    def decide(self, principal: AccessPrincipal, operation: AccessOperation) -> AccessDecision: ...


__all__ = [
    "AccessControllerPort", "AccessDecision", "AccessOperation", "AccessPrincipal",
]
