"""Human-only Artifacts authoring tools."""
from __future__ import annotations

import os
from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, authoring, fail
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    ArtifactRevisionInput, CommentOutput, CommentRevisionInput, DeleteOutput,
)
from .support import authority


def authoring_enabled() -> bool:
    return os.getenv("ARTIFACTS_ENABLE_AUTHORING_TOOLS", "").lower() in {
        "1", "true", "yes",
    }


def _allowed(actor: str):
    if actor != "human":
        return fail("artifact_human_required")
    if not authoring_enabled():
        return fail("authoring_disabled")
    return None


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @authoring(input_model=CommentRevisionInput, output_model=CommentOutput)
    def artifacts_resolve_comment(
        slug: str, comment_id: str, expected_revision: int,
    ) -> ToolResult[CommentOutput]:
        tenant, owner, actor = authority()
        denied = _allowed(actor)
        if denied:
            return denied
        comment = get_runtime().comments.resolve(
            tenant, owner, slug, comment_id, expected_revision, actor,
        )
        return CommentOutput(comment=comment)

    @typed_tool(mcp)
    @authoring(input_model=CommentRevisionInput, output_model=DeleteOutput)
    def artifacts_delete_comment(
        slug: str, comment_id: str, expected_revision: int,
    ) -> ToolResult[DeleteOutput]:
        tenant, owner, actor = authority()
        denied = _allowed(actor)
        if denied:
            return denied
        get_runtime().comments.delete(
            tenant, owner, slug, comment_id, expected_revision, actor,
        )
        return DeleteOutput(id=comment_id, deleted=True)

    @typed_tool(mcp)
    @authoring(input_model=ArtifactRevisionInput, output_model=DeleteOutput)
    def artifacts_purge(
        slug: str, expected_revision: int,
    ) -> ToolResult[DeleteOutput]:
        tenant, owner, actor = authority()
        denied = _allowed(actor)
        if denied:
            return denied
        get_runtime().lifecycle.purge(
            tenant, owner, slug, expected_revision, actor,
        )
        return DeleteOutput(id=slug, deleted=True)


__all__ = ["authoring_enabled", "register"]
