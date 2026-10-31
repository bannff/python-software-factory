"""Typed operational artifact organization tools."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts import (
    ArtifactMoveInput, ArtifactMoveOutput, DeleteOutput, FolderCreateInput,
    FolderMoveInput, FolderOutput, FolderRenameInput, FolderRevisionInput,
)
from .events import emit_artifact_event
from .support import authority


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=FolderCreateInput, output_model=FolderOutput)
    def artifacts_folder_create(
        name: str, parent_id: str | None = None,
    ) -> ToolResult[FolderOutput]:
        tenant, owner, _ = authority()
        return FolderOutput(folder=get_runtime().organization.create(
            tenant, owner, name, parent_id,
        ))

    @typed_tool(mcp)
    @operational(input_model=FolderRenameInput, output_model=FolderOutput)
    def artifacts_folder_rename(
        folder_id: str, expected_revision: int, name: str,
    ) -> ToolResult[FolderOutput]:
        tenant, owner, _ = authority()
        return FolderOutput(folder=get_runtime().organization.rename(
            tenant, owner, folder_id, expected_revision, name,
        ))

    @typed_tool(mcp)
    @operational(input_model=FolderMoveInput, output_model=FolderOutput)
    def artifacts_folder_move(
        folder_id: str, expected_revision: int,
        parent_id: str | None = None,
    ) -> ToolResult[FolderOutput]:
        tenant, owner, _ = authority()
        return FolderOutput(folder=get_runtime().organization.move(
            tenant, owner, folder_id, expected_revision, parent_id,
        ))

    @typed_tool(mcp)
    @operational(input_model=FolderRevisionInput, output_model=DeleteOutput)
    def artifacts_folder_delete(
        folder_id: str, expected_revision: int,
    ) -> ToolResult[DeleteOutput]:
        tenant, owner, _ = authority()
        get_runtime().organization.delete(
            tenant, owner, folder_id, expected_revision,
        )
        return DeleteOutput(id=folder_id, deleted=True)

    @typed_tool(mcp)
    @operational(input_model=ArtifactMoveInput, output_model=ArtifactMoveOutput)
    async def artifacts_move(
        slug: str, expected_revision: int, folder_id: str | None = None,
    ) -> ToolResult[ArtifactMoveOutput]:
        tenant, owner, _ = authority()
        artifact = get_runtime().organization.move_artifact(
            tenant, owner, slug, expected_revision, folder_id,
        )
        published = await emit_artifact_event(
            artifact, "artifact.moved", folder_id=folder_id,
        )
        return ArtifactMoveOutput(
            artifact=artifact, event_published=published,
            warning=None if published else "artifact_event_unavailable",
        )


__all__ = ["register"]
