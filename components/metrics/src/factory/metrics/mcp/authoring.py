"""Typed authoring MCP tools for Metrics."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any
from factory.mcp_utils.interface import ToolResult, authoring, ok
from factory.mcp_utils.registration import typed_tool

from ..authoring import AuthoringError, AuthoringManager
from ..runtime.models import MetricDefinition
from .contracts.authoring import (
    AuthoringStatusOutput, DefineMetricOutput, DefinitionInput, DeleteDefinitionInput,
    DeleteDefinitionOutput, EmptyInput, SetBaselineInput, SetBaselineOutput,
    UpdateDefinitionInput, UpdateDefinitionOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import MetricsRuntime


def _result(value: dict[str, Any], model: type[Any]) -> ToolResult[Any]:
    return ok(model.model_validate(value))


def register(mcp: Any, runtime: "MetricsRuntime", manager: AuthoringManager | None, enable_authoring: bool) -> None:
    """Register authoring tools; disabled mode remains successful domain data."""

    @typed_tool(mcp)
    @authoring(input_model=EmptyInput, output_model=AuthoringStatusOutput)
    def metrics_authoring_status() -> ToolResult[AuthoringStatusOutput]:
        return _result({"enabled": enable_authoring, "env_var": "METRICS_ENABLE_AUTHORING_TOOLS"}, AuthoringStatusOutput)

    @typed_tool(mcp)
    @authoring(input_model=DefinitionInput, output_model=DefineMetricOutput)
    def metrics_define_metric(definition: dict[str, Any]) -> ToolResult[DefineMetricOutput]:
        raw_definition = DefinitionInput.model_validate({"definition": definition}).definition.model_dump(mode="json")
        if not manager:
            return _result({"ok": False, "error": "authoring_disabled"}, DefineMetricOutput)
        try:
            defn = MetricDefinition.model_validate(raw_definition)
            runtime.register_definition(defn)
            persisted = manager.write_definition(raw_definition).get("ok", False)
            return _result({"ok": True, "id": defn.id, "persisted": persisted}, DefineMetricOutput)
        except (AuthoringError, Exception) as exc:
            return _result({"ok": False, "error": str(exc)}, DefineMetricOutput)

    @typed_tool(mcp)
    @authoring(input_model=UpdateDefinitionInput, output_model=UpdateDefinitionOutput)
    def metrics_update_definition(metric_id: str, updates: dict[str, Any]) -> ToolResult[UpdateDefinitionOutput]:
        patch = UpdateDefinitionInput.model_validate({"metric_id": metric_id, "updates": updates}).updates
        if not manager:
            return _result({"ok": False, "error": "authoring_disabled"}, UpdateDefinitionOutput)
        try:
            updated = runtime.update_definition(metric_id, patch.model_dump(exclude_unset=True))
            if updated is None:
                return _result({"ok": False, "error": f"Definition not found: {metric_id}"}, UpdateDefinitionOutput)
            definition = updated.model_dump(mode="json")
            manager.write_definition(definition)
            return _result({"ok": True, "id": metric_id, "definition": definition}, UpdateDefinitionOutput)
        except (AuthoringError, Exception) as exc:
            return _result({"ok": False, "error": str(exc)}, UpdateDefinitionOutput)

    @typed_tool(mcp)
    @authoring(input_model=DeleteDefinitionInput, output_model=DeleteDefinitionOutput)
    def metrics_delete_definition(metric_id: str) -> ToolResult[DeleteDefinitionOutput]:
        if not manager:
            return _result({"ok": False, "error": "authoring_disabled"}, DeleteDefinitionOutput)
        try:
            if not runtime.delete_definition(metric_id):
                return _result({"ok": False, "error": f"Definition not found: {metric_id}"}, DeleteDefinitionOutput)
            manager.delete_definition(metric_id)
            return _result({"ok": True, "id": metric_id, "deleted": True}, DeleteDefinitionOutput)
        except AuthoringError as exc:
            return _result({"ok": False, "error": str(exc)}, DeleteDefinitionOutput)

    @typed_tool(mcp)
    @authoring(input_model=SetBaselineInput, output_model=SetBaselineOutput)
    def metrics_set_baseline(metric_id: str, tag: str, values: dict[str, float]) -> ToolResult[SetBaselineOutput]:
        if not manager:
            return _result({"ok": False, "error": "authoring_disabled"}, SetBaselineOutput)
        return _result(runtime.set_baseline(metric_id, tag, values), SetBaselineOutput)
