"""Trusted content-free KB relationship projection."""
from __future__ import annotations

import hashlib
import logging
from typing import Any

from factory.mcp_utils.interface import (
    get_envelope, get_service, protected_canonical_json,
)

logger = logging.getLogger(__name__)


def emit_kb_projection(
    document_id: str, *, content_digest: str, references: list[dict[str, Any]],
    tenant_id: str | None, principal_id: str | None,
    action: str = "upsert",
) -> None:
    ambient = get_envelope() or {}
    tenant = ambient.get("tenant_id") or tenant_id
    owner = ambient.get("principal_id") or principal_id
    if not isinstance(tenant, str) or not isinstance(owner, str):
        logger.warning("KB Graph projection skipped: identity unavailable")
        return
    factory = get_service("tool_invoker_for_caller")
    invoke = factory("kb") if callable(factory) else None
    if not callable(invoke):
        logger.warning("KB Graph projection skipped: Events unavailable")
        return
    record = {
        "source_system": "kb", "action": action,
        "subject_kind": "kb", "subject_local_id": document_id,
        "subject_type": "KBDocument", "source_digest": content_digest,
        "references": references if action == "upsert" else [],
    }
    digest = hashlib.sha256(protected_canonical_json(record)).hexdigest()
    binding = {
        "tenant_id": tenant, "owner_id": owner,
        "event_type": "graph.projection.requested",
        "subject_id": document_id, "revision": 1,
        "payload_digest": digest,
    }
    raw = invoke(
        {"brick_name": "events", "tool_name": "events_publish_projection"},
        arguments={**binding, "record": record},
        idempotency_key=f"kb-projection:{document_id}:{action}:1",
        envelope={"tenant_id": tenant, "principal_id": owner},
        projection=binding,
    )
    structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        logger.warning("KB Graph projection failed")


def digest_content(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def digest_tombstone(document_id: str) -> str:
    return hashlib.sha256(protected_canonical_json({
        "document_id": document_id, "deleted": True,
    })).hexdigest()


__all__ = ["digest_content", "digest_tombstone", "emit_kb_projection"]
