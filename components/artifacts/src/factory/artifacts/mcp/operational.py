"""Typed operational Artifacts lifecycle."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.models import ArtifactKind
from .contracts import (
    ArtifactRevisionInput, ArtifactWriteOutput, RevertArtifactInput,
    SaveArtifactInput, TombstoneOutput, UpdateArtifactInput,
)
from .events import emit_artifact_event
from .support import authority


def _event_output(result, published: bool) -> ArtifactWriteOutput:
    return ArtifactWriteOutput(
        result=result, event_published=published,
        warning=None if published else "artifact_event_unavailable",
    )


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SaveArtifactInput, output_model=ArtifactWriteOutput)
    async def artifacts_save(
        name: str, content: str, description: str = "", kind: str = "markdown",
        tags: list[str] | None = None, idempotency_key: str | None = None,
    ) -> ToolResult[ArtifactWriteOutput]:
        tenant, owner, actor = authority()
        result = get_runtime().lifecycle.save(
            tenant, owner, name, content, description=description,
            kind=ArtifactKind(kind), tags=tuple(tags or ()), actor_kind=actor,
            idempotency_key=idempotency_key,
        )
        if result.outcome == "matched":
            return ArtifactWriteOutput(result=result)
        published = await emit_artifact_event(result.artifact, "artifact.created")
        return _event_output(result, published)

    @typed_tool(mcp)
    @operational(input_model=UpdateArtifactInput, output_model=ArtifactWriteOutput)
    async def artifacts_update(
        slug: str, expected_revision: int, name: str | None = None,
        content: str | None = None, description: str | None = None,
        kind: str | None = None, tags: list[str] | None = None,
    ) -> ToolResult[ArtifactWriteOutput]:
        tenant, owner, actor = authority()
        result = get_runtime().lifecycle.update(
            tenant, owner, slug, expected_revision, actor_kind=actor,
            name=name, content=content, description=description,
            kind=ArtifactKind(kind) if kind else None,
            tags=tuple(tags) if tags is not None else None,
        )
        return _event_output(
            result, await emit_artifact_event(result.artifact, "artifact.updated"),
        )

    @typed_tool(mcp)
    @operational(input_model=RevertArtifactInput, output_model=ArtifactWriteOutput)
    async def artifacts_revert(
        slug: str, version: int, expected_revision: int,
    ) -> ToolResult[ArtifactWriteOutput]:
        tenant, owner, actor = authority()
        result = get_runtime().lifecycle.revert(
            tenant, owner, slug, version, expected_revision, actor,
        )
        return _event_output(
            result, await emit_artifact_event(result.artifact, "artifact.reverted"),
        )

    @typed_tool(mcp)
    @operational(input_model=ArtifactRevisionInput, output_model=TombstoneOutput)
    async def artifacts_tombstone(
        slug: str, expected_revision: int,
    ) -> ToolResult[TombstoneOutput]:
        tenant, owner, _ = authority()
        event_record = get_runtime().lifecycle.tombstone(
            tenant, owner, slug, expected_revision,
        )
        published = await emit_artifact_event(event_record, "artifact.deleted")
        return TombstoneOutput(
            slug=slug, tombstoned=True, event_published=published,
            warning=None if published else "artifact_event_unavailable",
        )


__all__ = ["register"]
