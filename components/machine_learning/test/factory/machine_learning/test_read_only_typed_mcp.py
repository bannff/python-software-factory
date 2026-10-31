"""Fresh-server contract coverage for ML's migrated read-only MCP families."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError

from factory.machine_learning.server import create_mcp_server
from factory.machine_learning.runtime.runtime import reset_runtime
from factory.mcp_utils.interface import ToolResult


TOOLS = {
    "ml_get_capabilities": {}, "ml_health_check": {},
    "ml_describe_config_schema": {}, "tracking_get_experiment": {"experiment_id": "missing"},
    "tracking_list_experiments": {}, "tracking_get_run": {"run_id": "missing"},
    "ml_list_learning_runs": {}, "ml_get_learning_run": {"run_id": "missing"},
    "ml_get_learning_summary": {}, "ml_get_learning_run_timeline": {"run_id": "missing"},
    "ml_get_learning_run_artifacts": {"run_id": "missing"}, "ml_list_training_runs": {},
    "ml_get_training_run": {"run_id": "missing"}, "ml_get_run_regression": {"run_id": "missing"},
    "ml_get_dashboard_summary": {}, "ml_get_observatory_summary": {},
    "ml_get_observatory_lineage": {}, "ml_get_views": {},
}


def _tool(server, name):
    return asyncio.run(server.get_tool(name))


def test_all_migrated_read_tools_use_strict_typed_envelopes():
    reset_runtime()
    server = create_mcp_server()
    for name, arguments in TOOLS.items():
        tool = _tool(server, name)
        assert tool is not None
        assert tool.fn._mcp_category == "deterministic"
        result = tool.fn(**arguments)
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert result.data is not None
        assert tool.fn._mcp_input_model.model_config["extra"] == "forbid"
        assert tool.fn._mcp_output_model is type(result.data)


def test_migrated_ingress_rejects_unknown_fields():
    server = create_mcp_server()
    with pytest.raises(SchemaMigrationError):
        _tool(server, "ml_get_views").fn(unexpected=True)
