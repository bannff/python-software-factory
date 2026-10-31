"""Immutable, transport-neutral server-surface identity planning contracts."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Literal


def _text(name: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be a non-empty string")


def _digest(facts: dict[str, object]) -> str:
    encoded = json.dumps(facts, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True, slots=True)
class ServerSurfaceIdentity:
    """Facts that identify exactly one composed MCP server surface."""

    entry_point: str
    route_bindings: tuple[str, ...]
    transport_bindings: tuple[Literal["in_process", "http", "stdio"], ...]
    process_lifecycle_id: str
    catalog_digest: str
    scope_digest: str
    policy_digest: str
    closure_digest: str
    digest: str = field(init=False)

    def __post_init__(self) -> None:
        for name in ("entry_point", "process_lifecycle_id", "catalog_digest", "scope_digest", "policy_digest", "closure_digest"):
            _text(name, getattr(self, name))
        if not self.route_bindings or not self.transport_bindings:
            raise ValueError("surface requires routes and transports")
        if len(set(self.route_bindings)) != len(self.route_bindings):
            raise ValueError("route bindings must be unique")
        if len(set(self.transport_bindings)) != len(self.transport_bindings):
            raise ValueError("transport bindings must be unique")
        facts = {
            "entry_point": self.entry_point,
            "routes": tuple(sorted(self.route_bindings)),
            "transports": tuple(sorted(self.transport_bindings)),
            "lifecycle": self.process_lifecycle_id,
            "catalog": self.catalog_digest,
            "scope": self.scope_digest,
            "policy": self.policy_digest,
            "closure": self.closure_digest,
        }
        object.__setattr__(self, "digest", _digest(facts))


@dataclass(frozen=True, slots=True)
class ServerCompositionPlan:
    """Declarative view plan bound to exactly one server-surface identity."""

    identity: ServerSurfaceIdentity
    discovery_mode: Literal["progressive", "flat"]
    selected_tools: frozenset[str]


__all__ = ["ServerCompositionPlan", "ServerSurfaceIdentity"]
