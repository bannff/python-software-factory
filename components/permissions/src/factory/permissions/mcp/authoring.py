"""Strict typed, security-gated authoring tools for Permissions."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from factory.mcp_utils.interface import ToolResult, authoring as authoring_decorator, ok
from factory.mcp_utils.registration import typed_tool
from factory.permissions.authoring import (
    AuthoringError, AuthoringManager, logical_policy_path, sanitized_validation_issue,
)

from .contracts import (
    AuthoringStatusOutput, DeletePolicyOutput, EmptyInput, Identifier, JsonObject,
    PolicyIdInput, UpsertPolicyInput, UpsertPolicyOutput, ValidatePoliciesOutput,
)

if TYPE_CHECKING:
    from factory.permissions.runtime.runtime import PermissionsRuntime


def _safe_error(value: object) -> str:
    allowed = {"authoring_disabled", "validation_error", "policy_write_error", "policy_delete_error"}
    return value if isinstance(value, str) and value in allowed else "validation_error"


def register(mcp: Any, runtime: "PermissionsRuntime", manager: AuthoringManager | None) -> None:
    """Register exactly four authoring tools when the server gate is open."""

    @typed_tool(mcp, name="permissions.authoring.get_status")
    @authoring_decorator(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_get_status() -> ToolResult[AuthoringStatusOutput]:
        """Get authoring status without exposing policy contents or host paths."""
        if manager is None:
            return ok(AuthoringStatusOutput(enabled=False, config_dir=".", allowed_paths=["policies"], schema_versions=[1]))
        raw = manager.get_status()
        return ok(AuthoringStatusOutput(
            enabled=bool(raw.get("enabled", False)), config_dir=".",
            allowed_paths=["policies"], schema_versions=[1],
        ))

    @typed_tool(mcp, name="permissions.authoring.validate_policies")
    @authoring_decorator(input_model=EmptyInput, output_model=ValidatePoliciesOutput)
    def authoring_validate_policies() -> ToolResult[ValidatePoliciesOutput]:
        """Validate policies and return bounded issue data."""
        if manager is None:
            return ok(ValidatePoliciesOutput(ok=False, count=0, errors=[]))
        raw = manager.validate_all_policies()
        issues = [sanitized_validation_issue(issue) for issue in raw.get("errors", [])]
        return ok(ValidatePoliciesOutput(
            ok=bool(raw.get("ok", False)), count=int(raw.get("count", 0)), errors=issues,
        ))

    @typed_tool(mcp, name="permissions.authoring.upsert_policy")
    @authoring_decorator(input_model=UpsertPolicyInput, output_model=UpsertPolicyOutput)
    def authoring_upsert_policy(
        id: Identifier, yaml_or_object: str | JsonObject, dry_run: bool = False,
    ) -> ToolResult[UpsertPolicyOutput]:
        """Create or update a policy, or return validation data without writing."""
        if manager is None:
            return ok(UpsertPolicyOutput(ok=False, dry_run=dry_run, error="authoring_disabled"))
        try:
            raw = manager.upsert_policy_definition(id=id, yaml_or_object=yaml_or_object, dry_run=dry_run)
        except AuthoringError:
            return ok(UpsertPolicyOutput(ok=False, dry_run=dry_run, error="validation_error"))
        return ok(UpsertPolicyOutput(
            ok=bool(raw.get("ok", False)), dry_run=bool(raw.get("dry_run", dry_run)),
            path=logical_policy_path(raw["path"]) if raw.get("path") else None,
            error=_safe_error(raw.get("error")) if raw.get("error") else None,
        ))

    @typed_tool(mcp, name="permissions.authoring.delete_policy")
    @authoring_decorator(input_model=PolicyIdInput, output_model=DeletePolicyOutput)
    def authoring_delete_policy(id: Identifier) -> ToolResult[DeletePolicyOutput]:
        """Delete a policy or return a successful not-found outcome."""
        if manager is None:
            return ok(DeletePolicyOutput(ok=False, deleted=False, error="authoring_disabled"))
        try:
            raw = manager.delete_policy_definition(id=id)
        except AuthoringError:
            return ok(DeletePolicyOutput(ok=False, deleted=False, error="validation_error"))
        return ok(DeletePolicyOutput(
            ok=bool(raw.get("ok", False)), deleted=bool(raw.get("deleted", False)),
            path=logical_policy_path(raw["path"]) if raw.get("path") else None,
            error=_safe_error(raw.get("error")) if raw.get("error") else None,
        ))


__all__ = ["register"]
