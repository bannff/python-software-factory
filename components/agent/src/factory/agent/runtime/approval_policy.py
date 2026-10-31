"""Owner-scoped opt-in tool approval policy for Agent execution."""
from __future__ import annotations

from threading import Lock
from typing import Protocol

from pydantic import BaseModel, ConfigDict, Field, field_validator

_MAX_TOOLS = 128
_MAX_NAME = 256


class ApprovalPolicy(BaseModel):
    """Tools that must pause for the existing approval card; empty is autonomy."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)

    tool_names: tuple[str, ...] = Field(default=(), max_length=_MAX_TOOLS)
    revision: int = Field(default=0, ge=0)

    @field_validator("tool_names")
    @classmethod
    def _valid_names(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value) or any(
            not name.strip() or len(name) > _MAX_NAME or "\x00" in name
            for name in value
        ):
            raise ValueError("invalid approval tool names")
        return value


class StaleApprovalPolicy(ValueError):
    """Raised when revision compare-and-swap fails."""


class ApprovalPolicyStore(Protocol):
    def get(self, tenant_id: str, owner_id: str) -> ApprovalPolicy: ...

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        tool_names: tuple[str, ...],
    ) -> ApprovalPolicy: ...


class InMemoryApprovalPolicyStore:
    """Reference store for tests and explicitly injected runtimes."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], ApprovalPolicy] = {}
        self._lock = Lock()

    def get(self, tenant_id: str, owner_id: str) -> ApprovalPolicy:
        with self._lock:
            return self._rows.get((tenant_id, owner_id), ApprovalPolicy())

    def update(
        self, tenant_id: str, owner_id: str, expected_revision: int, *,
        tool_names: tuple[str, ...],
    ) -> ApprovalPolicy:
        with self._lock:
            current = self._rows.get((tenant_id, owner_id), ApprovalPolicy())
            if current.revision != expected_revision:
                raise StaleApprovalPolicy("stale approval policy")
            result = ApprovalPolicy(tool_names=tool_names, revision=current.revision + 1)
            self._rows[(tenant_id, owner_id)] = result
            return result


__all__ = [
    "ApprovalPolicy", "ApprovalPolicyStore", "InMemoryApprovalPolicyStore",
    "StaleApprovalPolicy",
]
