"""Typed authoring MCP tools for Auth."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from pydantic import JsonValue
from factory.mcp_utils.interface import ToolResult, authoring, fail

from ..authoring import AuthoringError, AuthoringManager
from .contracts.models import (
    AuthoringOperationOutput, AuthoringStatusOutput, DeleteBackendConfigInput,
    EmptyInput, UpsertBackendConfigInput, ValidateBackendConfigInput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import AuthRuntime


def register(mcp: Any, runtime: "AuthRuntime", manager: AuthoringManager | None) -> None:
    """Register authoring tools with strict public contracts."""

    @mcp.tool(name="auth.authoring.get_status")
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        raw = manager.get_status() if manager else {
            "enabled": False, "config_dir": str(runtime.config_dir),
            "allowed_paths": [], "schema_versions": [],
        }
        return AuthoringStatusOutput.model_validate(raw)

    @mcp.tool(name="auth.authoring.validate_backend_config")
    @authoring(input_model=ValidateBackendConfigInput, output_model=AuthoringOperationOutput)
    def authoring_validate_backend_config(dry_run: bool = True) -> ToolResult[AuthoringOperationOutput]:
        if not manager:
            return AuthoringOperationOutput(ok=False, error="authoring_disabled")
        try:
            raw = manager.validate_all_backends(best_effort_network=not dry_run)
            return AuthoringOperationOutput(ok=bool(raw.get("ok")), error=None if raw.get("ok") else "validation_failed", count=raw.get("count"), error_count=len(raw.get("errors", [])))
        except Exception:
            return fail("auth_authoring_error")

    @mcp.tool(name="auth.authoring.upsert_backend_config")
    @authoring(input_model=UpsertBackendConfigInput, output_model=AuthoringOperationOutput)
    def authoring_upsert_backend_config(name: str, yaml_or_object: JsonValue, dry_run: bool = False) -> ToolResult[AuthoringOperationOutput]:
        if not manager:
            return AuthoringOperationOutput(ok=False, error="authoring_disabled")
        try:
            raw = manager.upsert_backend_config(name, yaml_or_object, dry_run=dry_run)
            return AuthoringOperationOutput(ok=bool(raw.get("ok")), dry_run=raw.get("dry_run"))
        except AuthoringError:
            return AuthoringOperationOutput(ok=False, error="authoring_error")
        except Exception:
            return fail("auth_authoring_error")

    @mcp.tool(name="auth.authoring.delete_backend_config")
    @authoring(input_model=DeleteBackendConfigInput, output_model=AuthoringOperationOutput)
    def authoring_delete_backend_config(name: str) -> ToolResult[AuthoringOperationOutput]:
        if not manager:
            return AuthoringOperationOutput(ok=False, error="authoring_disabled")
        try:
            raw = manager.delete_backend_config(name)
            return AuthoringOperationOutput(ok=bool(raw.get("ok")), deleted=raw.get("deleted"))
        except AuthoringError:
            return AuthoringOperationOutput(ok=False, error="authoring_error")
        except Exception:
            return fail("auth_authoring_error")
