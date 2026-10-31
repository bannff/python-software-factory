"""Typed deterministic Artifacts reads."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from ..runtime.models import ArtifactKind
from .contracts import (
    ArtifactOutput, ArtifactRefInput, ArtifactsOutput, ArtifactVersionsOutput,
    CommentsOutput, EmptyInput, FoldersOutput, ListArtifactsInput,
)
from .support import authority


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ArtifactRefInput, output_model=ArtifactOutput)
    def artifacts_get(slug: str) -> ToolResult[ArtifactOutput]:
        tenant, owner, _ = authority()
        return ArtifactOutput(artifact=get_runtime().lifecycle.get(tenant, owner, slug))

    @typed_tool(mcp)
    @deterministic(input_model=ListArtifactsInput, output_model=ArtifactsOutput)
    def artifacts_list(
        limit: int = 100, offset: int = 0, name: str | None = None,
        kind: str | None = None, tag: str | None = None,
    ) -> ToolResult[ArtifactsOutput]:
        tenant, owner, _ = authority()
        return ArtifactsOutput(artifacts=get_runtime().lifecycle.list(
            tenant, owner, limit=limit, offset=offset, name=name,
            kind=ArtifactKind(kind) if kind else None, tag=tag,
        ))

    @typed_tool(mcp)
    @deterministic(input_model=ArtifactRefInput, output_model=ArtifactVersionsOutput)
    def artifacts_versions(slug: str) -> ToolResult[ArtifactVersionsOutput]:
        tenant, owner, _ = authority()
        return ArtifactVersionsOutput(
            versions=get_runtime().lifecycle.versions(tenant, owner, slug),
        )

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=FoldersOutput)
    def artifacts_folder_list() -> ToolResult[FoldersOutput]:
        tenant, owner, _ = authority()
        return FoldersOutput(
            folders=get_runtime().organization.list(tenant, owner),
        )

    @typed_tool(mcp)
    @deterministic(input_model=ArtifactRefInput, output_model=CommentsOutput)
    def artifacts_get_comments(slug: str) -> ToolResult[CommentsOutput]:
        tenant, owner, _ = authority()
        return CommentsOutput(
            comments=get_runtime().comments.list(tenant, owner, slug),
        )


__all__ = ["register"]
