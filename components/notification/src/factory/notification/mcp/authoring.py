"""Strict typed authoring MCP tools for Notification."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from factory.mcp_utils.interface import ToolResult, authoring, ok
from factory.mcp_utils.registration import typed_tool

from ..authoring import AuthoringError, AuthoringRuntime
from .contracts.inputs import (
    ChannelIdentifierInput, EmptyInput, TemplateIdentifierInput, UpsertChannelInput,
    UpsertTemplateInput,
)
from .contracts.outputs import AuthoringMutationOutput, AuthoringStatusOutput

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def _disabled() -> ToolResult[AuthoringMutationOutput]:
    return ok(AuthoringMutationOutput(ok=False, error="authoring_disabled"))


def _rejected() -> ToolResult[AuthoringMutationOutput]:
    return ok(AuthoringMutationOutput(ok=False, error="authoring_rejected"))


def register(
    mcp: Any, runtime: "NotificationRuntime", authoring_runtime: AuthoringRuntime | None,
    authoring_enabled: bool,
) -> None:
    """Register authoring tools with strict flat ingress and safe typed outcomes."""

    @typed_tool(mcp)
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_status() -> ToolResult[AuthoringStatusOutput]:
        """Return authoring availability without exposing config paths."""
        EmptyInput.model_validate({})
        return ok(AuthoringStatusOutput(enabled=authoring_enabled, env_var="NOTIFY_ENABLE_AUTHORING_TOOLS"))

    @typed_tool(mcp)
    @authoring(input_model=UpsertChannelInput, output_model=AuthoringMutationOutput)
    def upsert_channel_config(
        channel_id: str, type: str, config: dict[str, Any], enabled: bool = True,
    ) -> ToolResult[AuthoringMutationOutput]:
        """Create or update channel config without returning filesystem paths."""
        parsed = UpsertChannelInput.model_validate({
            "channel_id": channel_id, "type": type, "config": config, "enabled": enabled,
        })
        if not authoring_runtime:
            return _disabled()
        try:
            authoring_runtime.upsert_channel(parsed.channel_id, {
                "type": parsed.type, "config": parsed.config, "enabled": parsed.enabled,
            })
            return ok(AuthoringMutationOutput(ok=True, written=True, identifier=parsed.channel_id))
        except AuthoringError:
            return _rejected()
        except Exception:
            return ToolResult(ok=False, error="notification_authoring_failed")

    @typed_tool(mcp)
    @authoring(input_model=ChannelIdentifierInput, output_model=AuthoringMutationOutput)
    def delete_channel_config(channel_id: str) -> ToolResult[AuthoringMutationOutput]:
        """Delete channel config; a missing config is a normal typed outcome."""
        parsed = ChannelIdentifierInput.model_validate({"channel_id": channel_id})
        if not authoring_runtime:
            return _disabled()
        try:
            deleted = authoring_runtime.delete_channel(parsed.channel_id)
            return ok(AuthoringMutationOutput(ok=True, deleted=deleted, identifier=parsed.channel_id))
        except AuthoringError:
            return _rejected()
        except Exception:
            return ToolResult(ok=False, error="notification_authoring_failed")

    @typed_tool(mcp)
    @authoring(input_model=UpsertTemplateInput, output_model=AuthoringMutationOutput)
    def upsert_template_config(
        template_id: str, name: str, body: str, subject: str | None = None,
        variables: list[str] | None = None,
    ) -> ToolResult[AuthoringMutationOutput]:
        """Create or update template config without returning filesystem paths."""
        parsed = UpsertTemplateInput.model_validate({
            "template_id": template_id, "name": name, "body": body,
            "subject": subject, "variables": variables,
        })
        if not authoring_runtime:
            return _disabled()
        try:
            authoring_runtime.upsert_template(parsed.template_id, {
                "name": parsed.name, "body": parsed.body, "subject": parsed.subject,
                "variables": parsed.variables or [],
            })
            return ok(AuthoringMutationOutput(ok=True, written=True, identifier=parsed.template_id))
        except AuthoringError:
            return _rejected()
        except Exception:
            return ToolResult(ok=False, error="notification_authoring_failed")

    @typed_tool(mcp)
    @authoring(input_model=TemplateIdentifierInput, output_model=AuthoringMutationOutput)
    def delete_template_config(template_id: str) -> ToolResult[AuthoringMutationOutput]:
        """Delete template config; a missing config is a normal typed outcome."""
        parsed = TemplateIdentifierInput.model_validate({"template_id": template_id})
        if not authoring_runtime:
            return _disabled()
        try:
            deleted = authoring_runtime.delete_template(parsed.template_id)
            return ok(AuthoringMutationOutput(ok=True, deleted=deleted, identifier=parsed.template_id))
        except AuthoringError:
            return _rejected()
        except Exception:
            return ToolResult(ok=False, error="notification_authoring_failed")
