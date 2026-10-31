"""Authoring (security-gated) MCP tools for telemetry module."""
from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, authoring
from factory.mcp_utils.registration import typed_tool

from ..authoring import AuthoringError, AuthoringManager
from .contracts.authoring import (
    AuthoringStatusOutput, ConfigListOutput, ListConfigsInput, MutationOutput,
    ReadConfigInput, ReadConfigOutput, WriteConfigInput, WriteMetricFileInput,
)
from .contracts.base import EmptyInput, JsonObject

if TYPE_CHECKING:
    from ..runtime.runtime import TelemetryRuntime


def register(mcp: Any, runtime: "TelemetryRuntime", manager: AuthoringManager | None,
             enable_authoring: bool) -> None:
    """Register authoring tools."""

    @typed_tool(mcp)
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def authoring_status() -> ToolResult[AuthoringStatusOutput]:
        """Check if authoring tools are enabled."""
        return {"enabled": enable_authoring, "config_dir": str(runtime.config_dir), "env_var": "TELEMETRY_ENABLE_AUTHORING_TOOLS"}

    @typed_tool(mcp)
    @authoring(input_model=ListConfigsInput, output_model=ConfigListOutput)
    def list_configs(kind: str) -> ToolResult[ConfigListOutput]:
        """List configuration files of a given kind (metrics, exporters)."""
        return {"configs": [] if manager is None else manager.list_items(kind)}

    @typed_tool(mcp)
    @authoring(input_model=ReadConfigInput, output_model=ReadConfigOutput)
    def read_config(kind: str, item_id: str) -> ToolResult[ReadConfigOutput]:
        """Read a specific configuration file."""
        if manager is None:
            return {"ok": False, "error": "authoring_disabled"}
        try:
            return {"ok": True, "kind": kind, "id": item_id, "config": manager.read_yaml(kind, item_id)}
        except AuthoringError as error:
            return {"ok": False, "error": str(error)}

    @typed_tool(mcp)
    @authoring(input_model=WriteConfigInput, output_model=MutationOutput)
    def write_config(kind: str, config: JsonObject) -> ToolResult[MutationOutput]:
        """Write a configuration file."""
        if manager is None:
            return {"ok": False, "error": "authoring_disabled"}
        try:
            return manager.write_yaml(kind, config)
        except AuthoringError as error:
            return {"ok": False, "error": str(error)}

    @typed_tool(mcp)
    @authoring(input_model=WriteMetricFileInput, output_model=MutationOutput)
    def write_metric_file(file_id: str, definitions: list[JsonObject]) -> ToolResult[MutationOutput]:
        """Write a metric definitions file."""
        if manager is None:
            return {"ok": False, "error": "authoring_disabled"}
        try:
            return manager.write_metric_file(file_id, definitions)
        except AuthoringError as error:
            return {"ok": False, "error": str(error)}

    @typed_tool(mcp)
    @authoring(input_model=ReadConfigInput, output_model=MutationOutput)
    def delete_config(kind: str, item_id: str) -> ToolResult[MutationOutput]:
        """Delete a configuration file."""
        if manager is None:
            return {"ok": False, "error": "authoring_disabled"}
        try:
            return manager.delete_yaml(kind, item_id)
        except AuthoringError as error:
            return {"ok": False, "error": str(error)}
