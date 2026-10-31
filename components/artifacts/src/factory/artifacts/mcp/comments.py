"""Typed operational artifact comment tools."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    CommentBodyInput, CommentOutput, CommentRefInput, CommentReplyInput,
)
from .events import emit_artifact_event
from .support import authority


async def _output(runtime, tenant: str, owner: str, slug: str,
                  comment) -> CommentOutput:
    artifact = runtime.lifecycle.get(tenant, owner, slug)
    published = await emit_artifact_event(
        artifact, "artifact.commented", comment_id=comment.id,
    )
    return CommentOutput(
        comment=comment, event_published=published,
        warning=None if published else "artifact_event_unavailable",
    )


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=CommentBodyInput, output_model=CommentOutput)
    async def artifacts_post_comment(
        slug: str, body: str, anchor_text: str | None = None,
    ) -> ToolResult[CommentOutput]:
        tenant, owner, actor = authority()
        runtime = get_runtime()
        comment = runtime.comments.post(
            tenant, owner, slug, body, actor, anchor_text=anchor_text,
        )
        return await _output(runtime, tenant, owner, slug, comment)

    @typed_tool(mcp)
    @operational(input_model=CommentReplyInput, output_model=CommentOutput)
    async def artifacts_reply_comment(
        slug: str, body: str, parent_id: str,
    ) -> ToolResult[CommentOutput]:
        tenant, owner, actor = authority()
        runtime = get_runtime()
        comment = runtime.comments.post(
            tenant, owner, slug, body, actor, parent_id,
        )
        return await _output(runtime, tenant, owner, slug, comment)

    @typed_tool(mcp)
    @operational(input_model=CommentRefInput, output_model=CommentOutput)
    async def artifacts_mark_comment_review(
        slug: str, comment_id: str,
    ) -> ToolResult[CommentOutput]:
        tenant, owner, _ = authority()
        runtime = get_runtime()
        comment = runtime.comments.mark_review(
            tenant, owner, slug, comment_id,
        )
        return await _output(runtime, tenant, owner, slug, comment)


__all__ = ["register"]
