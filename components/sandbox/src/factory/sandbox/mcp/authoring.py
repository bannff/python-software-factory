"""Typed, authoring-gated Sandbox template management tools."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import Field

from factory.mcp_utils.interface import authoring as authoring_decorator, fail, ok
from .contracts import EmptyInput, StrictModel
from factory.mcp_utils.runtime.tool_result import ToolResult

if TYPE_CHECKING:
    from ..authoring import AuthoringManager
    from ..runtime.runtime import SandboxRuntime


class AuthoringStatusResult(StrictModel):
    enabled: bool
    config_dir: str | None = None
    allowed_paths: list[str] = Field(default_factory=list)
    message: str | None = None


class TemplateRecord(StrictModel):
    id: str
    path: str
    config: dict[str, Any] | None = None
    error: str | None = None


class TemplateListResult(StrictModel):
    templates: list[TemplateRecord] = Field(default_factory=list)
    count: int = Field(default=0, ge=0)


class UpsertTemplateRequest(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")
    config: dict[str, Any]
    dry_run: bool = False


class TemplateWriteResult(StrictModel):
    success: bool
    dry_run: bool = False
    path: str
    deleted: bool | None = None


class TemplateIdRequest(StrictModel):
    id: str = Field(min_length=1, max_length=128, pattern=r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,127}$")


def register(mcp: Any, runtime: "SandboxRuntime", manager: "AuthoringManager | None") -> None:
    """Register typed authoring tools; disabled mode returns ToolResult failures."""

    @mcp.tool(name="sandbox.authoring.get_status")
    @authoring_decorator(input_model=EmptyInput, output_model=AuthoringStatusResult)
    def authoring_get_status() -> ToolResult[AuthoringStatusResult]:
        """Return authoring gate status."""
        if manager is None:
            return ok(AuthoringStatusResult(enabled=False, message="Authoring tools disabled"))
        return ok(AuthoringStatusResult.model_validate(manager.get_status()))

    @mcp.tool(name="sandbox.authoring.list_templates")
    @authoring_decorator(input_model=EmptyInput, output_model=TemplateListResult)
    def authoring_list_templates() -> ToolResult[TemplateListResult]:
        """List managed environment templates."""
        if manager is None:
            return fail("Authoring tools disabled")
        return ok(TemplateListResult.model_validate(manager.list_templates()))

    @mcp.tool(name="sandbox.authoring.upsert_template")
    @authoring_decorator(input_model=UpsertTemplateRequest, output_model=TemplateWriteResult)
    def authoring_upsert_template(
        id: str = Field(min_length=1, max_length=128), config: dict[str, Any] = Field(...),
        dry_run: bool = False,
    ) -> ToolResult[TemplateWriteResult]:
        """Create or update a template."""
        if manager is None:
            return fail("Authoring tools disabled")
        raw = manager.upsert_template(id=id, config=config, dry_run=dry_run)
        return ok(TemplateWriteResult(success=raw["ok"], dry_run=raw["dry_run"], path=raw["path"]))

    @mcp.tool(name="sandbox.authoring.delete_template")
    @authoring_decorator(input_model=TemplateIdRequest, output_model=TemplateWriteResult)
    def authoring_delete_template(id: str = Field(min_length=1, max_length=128)) -> ToolResult[TemplateWriteResult]:
        """Delete a managed template."""
        if manager is None:
            return fail("Authoring tools disabled")
        raw = manager.delete_template(id=id)
        return ok(TemplateWriteResult(success=raw["ok"], path=raw["path"], deleted=raw["deleted"]))
