"""Authority-scoped graph neighborhood contracts and identity helpers."""
from __future__ import annotations

import base64
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from .ports import Entity, Relationship

_COMPONENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._@|:-]{0,127}")
_KIND = re.compile(r"[a-z][a-z0-9-]{0,31}")


@dataclass(frozen=True, slots=True)
class NeighborhoodRequest:
    seed_ids: tuple[str, ...]
    tenant_id: str
    principal_id: str
    relationship_types: tuple[str, ...] = ()
    direction: str = "both"
    max_depth: int = 1
    node_limit: int = 100
    edge_limit: int = 200


@dataclass(frozen=True, slots=True)
class NeighborhoodResult:
    entities: tuple[Entity, ...] = ()
    relationships: tuple[Relationship, ...] = ()
    depth_reached: int = 0
    nodes_truncated: bool = False
    edges_truncated: bool = False


class NeighborhoodPort(Protocol):
    def get_neighborhood(self, request: NeighborhoodRequest) -> NeighborhoodResult:
        """Return a bounded same-authority subgraph around canonical seeds."""
        ...


def encode_node_id(kind: str, tenant_id: str, principal_id: str, local_id: str) -> str:
    if not _KIND.fullmatch(kind):
        raise ValueError("invalid node kind")
    return "~".join((kind, *(_encode(value) for value in (
        tenant_id, principal_id, local_id,
    ))))


def decode_node_id(node_id: str) -> tuple[str, str, str, str]:
    parts = node_id.split("~")
    if len(parts) != 4 or not _KIND.fullmatch(parts[0]):
        raise ValueError("invalid canonical node id")
    values = tuple(_decode(value) for value in parts[1:])
    if encode_node_id(parts[0], *values) != node_id:
        raise ValueError("non-canonical node id")
    return parts[0], *values


def matches_authority(node_id: str, tenant_id: str, principal_id: str) -> bool:
    try:
        _kind, tenant, principal, _local = decode_node_id(node_id)
    except ValueError:
        return False
    return tenant == tenant_id and principal == principal_id


def authority_tokens(tenant_id: str, principal_id: str) -> tuple[str, str]:
    return _encode(tenant_id), _encode(principal_id)


def validate_request(request: NeighborhoodRequest) -> None:
    _validate_component(request.tenant_id)
    _validate_component(request.principal_id)
    if not request.seed_ids or len(request.seed_ids) > 20:
        raise ValueError("seed count must be 1..20")
    if request.direction not in {"in", "out", "both"}:
        raise ValueError("invalid direction")
    if not 1 <= request.max_depth <= 3:
        raise ValueError("max_depth must be 1..3")
    if not len(request.seed_ids) <= request.node_limit <= 200:
        raise ValueError("node_limit must include every seed and be <= 200")
    if not 1 <= request.edge_limit <= 400:
        raise ValueError("edge_limit must be 1..400")
    for value in request.relationship_types:
        _validate_component(value)
    if any(not matches_authority(value, request.tenant_id, request.principal_id)
           for value in request.seed_ids):
        raise ValueError("invalid or foreign seed")


def _validate_component(value: str) -> None:
    if not isinstance(value, str) or not _COMPONENT.fullmatch(value):
        raise ValueError("invalid identity component")


def _encode(value: str) -> str:
    _validate_component(value)
    return base64.urlsafe_b64encode(value.encode()).decode().rstrip("=")


def _decode(value: str) -> str:
    if not value or not re.fullmatch(r"[A-Za-z0-9_-]+", value):
        raise ValueError("invalid encoded node id")
    try:
        decoded = base64.urlsafe_b64decode(value + "=" * (-len(value) % 4)).decode()
    except Exception as exc:
        raise ValueError("invalid encoded node id") from exc
    _validate_component(decoded)
    return decoded


__all__ = [
    "NeighborhoodPort", "NeighborhoodRequest", "NeighborhoodResult",
    "authority_tokens", "decode_node_id", "encode_node_id",
    "matches_authority", "validate_request",
]
