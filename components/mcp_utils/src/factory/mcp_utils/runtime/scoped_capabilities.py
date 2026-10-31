"""Framework-neutral contracts for scoped MCP capabilities."""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
from typing import Any, Iterable, Protocol


@dataclass(frozen=True)
class CapabilityScope:
    """Trusted capability policy bound to one execution."""

    policy_id: str
    digest: str
    tool_names: frozenset[str]
    delegation_depth: int = 0

    @classmethod
    def create(
        cls, policy_id: str, tool_names: Iterable[str], *,
        delegation_depth: int = 0, digest: str | None = None,
    ) -> "CapabilityScope":
        """Mint canonical authority or reject a mismatched supplied digest."""
        names = frozenset(tool_names)
        if not policy_id or delegation_depth < 0:
            raise ValueError("capability policy and delegation depth must be valid")
        if any(not isinstance(name, str) or not name for name in names):
            raise ValueError("capability tool names must be non-empty strings")
        expected = canonical_scope_digest(policy_id, names, delegation_depth)
        if digest is not None and digest != expected:
            raise ValueError("capability scope digest mismatch")
        return cls(policy_id, expected, names, delegation_depth)


def canonical_scope_digest(
    policy_id: str, tool_names: Iterable[str], delegation_depth: int,
) -> str:
    """Digest sorted names with the trusted policy and delegation depth."""
    payload = {
        "delegation_depth": delegation_depth,
        "policy_id": policy_id,
        "tool_names": sorted(tool_names),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CapabilityDescriptor:
    """An allowlisted MCP capability exposed to a runtime adapter."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class CapabilityInvocation:
    """A scoped tool request with replay-safe correlation metadata."""

    name: str
    arguments: dict[str, Any]
    idempotency_key: str
    correlation: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class CapabilityResult:
    """A normalized capability response that preserves structured content."""

    content: tuple[dict[str, Any], ...]
    structured_content: dict[str, Any] | None = None
    is_error: bool = False


class ScopedCapabilityClientPort(Protocol):
    """The sole capability transport available to runtime adapters."""

    @property
    def scope(self) -> CapabilityScope:
        """Return the immutable trusted scope for this client."""
        ...

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """List only capabilities admitted by ``scope``."""
        ...

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
        """Invoke one allowlisted capability through the native MCP path."""
        ...

    async def close(self) -> None:
        """Release every transport/session resource deterministically."""
        ...
