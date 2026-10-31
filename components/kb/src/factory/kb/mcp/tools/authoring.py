"""Typed authoring MCP tools for the KB brick."""

from __future__ import annotations

from typing import Any, Callable

from pydantic import Field

from factory.mcp_utils.interface import authoring, ok
from factory.mcp_utils.runtime.tool_result import ToolResult

from ...models.surface import (
    KbAuthoringDeleteRequest,
    KbAuthoringResult,
    KbAuthoringStatusResult,
    KbAuthoringUpsertRequest,
    KbAuthoringValidateRequest,
    KbEmptyRequest,
)


def register(mcp: Any, get_authoring: Callable[[], Any]) -> None:
    """Register typed KB authoring tools; runtime authoring gates remain intact."""

    @mcp.tool(name="authoring.get_status")
    @authoring(input_model=KbEmptyRequest, output_model=KbAuthoringStatusResult)
    def authoring_get_status() -> ToolResult[KbAuthoringStatusResult]:
        """Get authoring status."""
        return ok(KbAuthoringStatusResult.model_validate(get_authoring().get_status()))

    @mcp.tool(name="authoring.validate_collections")
    @authoring(
        input_model=KbAuthoringValidateRequest,
        output_model=KbAuthoringResult,
    )
    def authoring_validate_collections(
        dry_run: bool = True,
    ) -> ToolResult[KbAuthoringResult]:
        """Validate collection configurations."""
        result = get_authoring().validate_collections(dry_run=dry_run)
        return ok(KbAuthoringResult.model_validate(result))

    @mcp.tool(name="authoring.upsert_collection")
    @authoring(
        input_model=KbAuthoringUpsertRequest,
        output_model=KbAuthoringResult,
    )
    def authoring_upsert_collection(
        collection_id: str = Field(min_length=1, max_length=128),
        collection_data: dict[str, Any] = Field(...),
        dry_run: bool = False,
    ) -> ToolResult[KbAuthoringResult]:
        """Create or update a collection configuration."""
        result = get_authoring().upsert_collection_config(
            collection_id, collection_data, dry_run=dry_run,
        )
        return ok(KbAuthoringResult.model_validate(result))

    @mcp.tool(name="authoring.delete_collection")
    @authoring(
        input_model=KbAuthoringDeleteRequest,
        output_model=KbAuthoringResult,
    )
    def authoring_delete_collection(
        collection_id: str = Field(min_length=1, max_length=128),
    ) -> ToolResult[KbAuthoringResult]:
        """Delete a collection configuration."""
        return ok(KbAuthoringResult.model_validate(
            get_authoring().delete_collection_config(collection_id)
        ))
