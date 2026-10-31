"""Target-native Memory import: digest-verified, owner-partitioned, idempotent.

M7 slice 2. The protected ``memory_import_record`` MCP tool is a thin
service-only shell; this module owns the logic so it is unit-testable without
the internal-invocation permit machinery.

Canonical target material (``target_digest`` recompute)
-------------------------------------------------------
``target_digest`` MUST equal the lowercase SHA-256 hex digest of
``protected_canonical_json`` over EXACTLY the following target-native material::

    {
        "tenant_id": <tenant_id>,
        "owner_id":  <owner_id>,
        "kind":      "memory",
        "subtype":   "semantic" | "episodic",
        "content":   <content>,
        "key":       <key>,
        "tags":      sorted(set(<tags>)),
    }

The digest is recomputed here and any drift from the declared binding digest
fails closed BEFORE any adapter write. The material is deliberately independent
of the source adapter/fingerprint/record identifiers and of provenance
metadata, so it names only the target-native record being written.

Partition, provenance, embeddings
----------------------------------
The adapter ``user_id`` is derived once through Memory's own partition
primitive (``derive_memory_user_id(owner_id, "global")``) — the structural
global partition. Owner isolation therefore holds by construction. Metadata
carries provenance IDENTIFIERS only (never a source filesystem path), and the
tag list preserves Memory's existing ``metadata.tags`` ANY-match semantics.
Embeddings are rebuilt by the target adapter from ``content`` (never copied
from the source) because the write goes through ``runtime.store``.
"""
from __future__ import annotations

import hashlib
from typing import Any, Callable

from factory.mcp_utils.interface import protected_canonical_json

from factory.memory.runtime.idempotency import store_once_with_outcome
from factory.memory.runtime.partition import derive_memory_user_id

# Structural global partition scope (M6.5 partition seam).
_GLOBAL_SCOPE = "global"
_REQUIRED_KIND = "memory"

# subtype -> (memory_type, category) target-native mapping.
_SUBTYPE_MAP: dict[str, tuple[str, str]] = {
    "semantic": ("long_term", "fact"),
    "episodic": ("episodic", "context"),
}

# Fixed, information-free safe errors.
ERR_KIND = "memory import kind unsupported"
ERR_SUBTYPE = "memory import subtype unsupported"
ERR_DIGEST = "memory import target digest mismatch"
ERR_UNAVAILABLE = "memory import store unavailable"


class MigrationImportError(ValueError):
    """Data-safe rejection carrying only a fixed public message."""

    def __init__(self, safe: str) -> None:
        super().__init__(safe)
        self.safe = safe


def canonical_target_digest(
    *, tenant_id: str, owner_id: str, kind: str, subtype: str,
    content: str, key: str, tags: Any,
) -> str:
    """Lowercase SHA-256 over the documented canonical target material."""
    material = {
        "tenant_id": tenant_id, "owner_id": owner_id, "kind": kind,
        "subtype": subtype, "content": content, "key": key,
        "tags": sorted({str(tag) for tag in tags}),
    }
    return hashlib.sha256(protected_canonical_json(material)).hexdigest()


def import_memory_record(
    runtime: Any, invoke: Callable[..., Any], *, tenant_id: str, owner_id: str,
    source_adapter: str, source_fingerprint: str, plan_digest: str, kind: str,
    source_record_id: str, target_digest: str, subtype: str, content: str,
    key: str, tags: Any,
) -> tuple[str, str]:
    """Import one record. Return ``(outcome, memory_id)``.

    ``outcome`` is ``"imported"`` for a fresh durable write or ``"replayed"``
    for a matched prior write of the same source record. Raises
    ``MigrationImportError`` (kind/subtype/digest) before any write.
    """
    if kind != _REQUIRED_KIND:
        raise MigrationImportError(ERR_KIND)
    mapping = _SUBTYPE_MAP.get(subtype)
    if mapping is None:
        raise MigrationImportError(ERR_SUBTYPE)
    memory_type, category = mapping
    tag_list = [str(tag) for tag in tags]
    actual = canonical_target_digest(
        tenant_id=tenant_id, owner_id=owner_id, kind=kind, subtype=subtype,
        content=content, key=key, tags=tag_list,
    )
    if actual != target_digest:
        raise MigrationImportError(ERR_DIGEST)
    user_id = derive_memory_user_id(owner_id, _GLOBAL_SCOPE)
    metadata = {
        "tags": tag_list,
        "import_source_adapter": source_adapter,
        "import_source_fingerprint": source_fingerprint,
        "import_plan_digest": plan_digest,
        "import_source_record_id": source_record_id,
        "import_target_digest": target_digest,
        "import_kind": kind,
        "import_key": key,
    }
    idempotency_key = f"migration-import:{source_adapter}:{source_record_id}"
    memory, replayed = store_once_with_outcome(
        runtime, invoke, idempotency_key=idempotency_key, user_id=user_id,
        content=content, memory_type=memory_type, category=category,
        metadata=metadata, ttl_seconds=None,
    )
    return ("replayed" if replayed else "imported"), memory.id


__all__ = [
    "ERR_DIGEST", "ERR_KIND", "ERR_SUBTYPE", "ERR_UNAVAILABLE",
    "MigrationImportError", "canonical_target_digest", "import_memory_record",
]
