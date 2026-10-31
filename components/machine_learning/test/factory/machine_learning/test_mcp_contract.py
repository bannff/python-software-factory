"""Contract tests for ML's typed MCP boundary."""
from __future__ import annotations

import asyncio
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult


def _result(name: str, **arguments):
    result = asyncio.run(create_mcp_server().get_tool(name)).fn(**arguments)
    assert isinstance(result, ToolResult) and result.ok is True
    return result.data


def test_contract_tools_return_typed_envelopes():
    caps = _result("ml_get_capabilities")
    health = _result("ml_health_check")
    schema = _result("ml_describe_config_schema")
    assert caps.name == "machine_learning"
    assert health.healthy is True
    assert schema.type == "object" and "backend" in schema.properties


def test_dataset_generation_surface_is_not_registered():
    server = create_mcp_server()
    for name in ("ml_get_stage_output", "ml_get_training_map", "ml_dataset_create_pipeline", "ml_dataset_run_pipeline"):
        assert asyncio.run(server.get_tool(name)) is None
