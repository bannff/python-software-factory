"""Strict content-free Artifacts lifecycle Events."""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import get_service

from ..runtime.models import ArtifactRecord

logger = logging.getLogger(__name__)
ArtifactEventType = Literal[
    "artifact.created", "artifact.updated", "artifact.reverted",
    "artifact.commented", "artifact.moved", "artifact.deleted",
]


class ArtifactAuthority(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    tenant_id: str = Field(min_length=1, max_length=256)
    principal_id: str = Field(min_length=1, max_length=256)


class ArtifactEventPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)
    authority: ArtifactAuthority
    slug: str
    version: int = Field(ge=1)
    revision: int = Field(ge=1)
    kind: str
    folder_id: str | None = None
    comment_id: str | None = None
    content_sha256: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


async def emit_artifact_event(
    artifact: ArtifactRecord, event_type: ArtifactEventType, *,
    folder_id: str | None = None, comment_id: str | None = None,
) -> bool:
    payload = ArtifactEventPayload(
        authority=ArtifactAuthority(
            tenant_id=artifact.tenant_id, principal_id=artifact.owner_id,
        ), slug=artifact.slug, version=artifact.version,
        revision=artifact.revision, kind=artifact.kind.value,
        folder_id=folder_id, comment_id=comment_id,
        content_sha256=(artifact.content_sha256 if event_type in {
            "artifact.created", "artifact.updated", "artifact.reverted",
        } else None),
    )
    try:
        factory = get_service("tool_invoker_for_caller")
        invoke = factory("artifacts") if callable(factory) else None
        if not callable(invoke):
            raise RuntimeError("Artifacts Events MCP unavailable")
        envelope = {"tenant_id": artifact.tenant_id,
                    "principal_id": artifact.owner_id}
        raw = await asyncio.to_thread(
            invoke, {"brick_name": "events", "tool_name": "events_publish"},
            arguments={"event_type": event_type,
                       "payload": payload.model_dump(mode="json"),
                       "source": "artifacts", "tenant_id": artifact.tenant_id,
                       "principal_id": artifact.owner_id},
            idempotency_key=(f"artifact-event:{event_type}:{artifact.slug}:"
                             f"{artifact.revision}"), envelope=envelope,
        )
        structured = raw.get("result", {}).get("structured_content") if isinstance(raw, dict) else None
        if not isinstance(structured, dict) or structured.get("ok") is not True:
            raise RuntimeError("Artifacts Events publication failed")
        return True
    except Exception as exc:
        logger.warning("artifact lifecycle event unavailable: %s", exc)
        return False


__all__ = ["ArtifactAuthority", "ArtifactEventPayload", "emit_artifact_event"]
