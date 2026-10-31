"""Strict Pydantic-v2 ingress and ToolResult egress for Learning."""
from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import pytest

from factory.learning.runtime.models import RewardSignal
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.learning.server import create_mcp_server
from factory.mcp_utils.interface import SchemaMigrationError, ToolResult


class _FixedSource:
    source_id = "fixed-test"

    def __init__(self, scalar: float) -> None:
        self._scalar = scalar

    def signal_or_none(self, _run_ctx: dict[str, Any], _invoker: Any) -> RewardSignal:
        return RewardSignal.from_scalar(
            self.source_id,
            self._scalar,
            provenance={"fixture": True},
            raw={"scoring": {"f1": max(0.0, self._scalar)}},
        )


def _server(scalar: float | None = None):
    registry = RewardSourceRegistry()
    if scalar is not None:
        registry.register_builtin(_FixedSource(scalar))
    return create_mcp_server(LearningRuntime(registry))


def _tool(server, name: str):
    return asyncio.run(server.get_tool(name)).fn


def test_catalog_categories_and_local_strict_contracts() -> None:
    server = _server()
    tools = {tool.name: tool for tool in asyncio.run(server.list_tools())}
    assert set(tools) == {"learning_list_reward_sources", "learning_compute_reward"}
    assert tools["learning_list_reward_sources"].fn._mcp_category == "deterministic"
    assert tools["learning_compute_reward"].fn._mcp_category == "operational"

    for tool in tools.values():
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__ == "factory.learning.mcp.contracts"
        assert output_model.__module__ == "factory.learning.mcp.contracts"
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert str(inspect.signature(tool.fn).return_annotation) == (
            f"ToolResult[{output_model.__name__}]"
        )
    assert inspect.signature(_tool(server, "learning_list_reward_sources")).parameters == {}


def test_flat_defaults_and_non_coercive_unknown_field_rejection() -> None:
    parameters = inspect.signature(_tool(_server(), "learning_compute_reward")).parameters
    expected = {
        "graph_id": "", "run_id": "", "vuln_class": "", "domain_class": "",
        "workflow_type": "auto", "target_app": "", "input_summary": "",
        "output_summary": "", "feedback_verdict": "", "tool_error_rate": None,
    }
    assert set(parameters) == set(expected)
    assert {name: parameters[name].default for name in expected} == expected

    compute = _tool(_server(), "learning_compute_reward")
    list_sources = _tool(_server(), "learning_list_reward_sources")
    with pytest.raises(SchemaMigrationError):
        compute(unexpected=True)
    with pytest.raises(SchemaMigrationError):
        list_sources(unexpected=True)
    with pytest.raises(SchemaMigrationError):
        compute(graph_id=1)
    with pytest.raises(SchemaMigrationError):
        compute(tool_error_rate="0.5")


def test_raw_transport_preserves_strict_wire_validation_and_typed_defaults() -> None:
    tool = asyncio.run(_server().get_tool("learning_compute_reward"))
    result = asyncio.run(tool.run({}))
    wire = json.loads(result.content[0].text)
    assert wire["schema_version"] == "v1"
    assert wire["ok"] is True
    assert wire["data"]["verdict"] == "no_reward"
    assert wire["data"]["scalar"] == 0.0

    list_tool = asyncio.run(_server(0.2).get_tool("learning_list_reward_sources"))
    listed = asyncio.run(list_tool.run({}))
    listed_wire = json.loads(listed.content[0].text)
    assert listed_wire["schema_version"] == "v1"
    assert listed_wire["ok"] is True
    assert listed_wire["data"]["source_ids"] == ["fixed-test"]

    with pytest.raises(Exception, match="Invalid arguments"):
        asyncio.run(tool.run({"tool_error_rate": "0.5"}))


def test_tools_return_typed_success_and_preserve_registry_output() -> None:
    server = _server(0.73)
    listed = _tool(server, "learning_list_reward_sources")()
    computed = _tool(server, "learning_compute_reward")(graph_id="g", run_id="r")

    assert isinstance(listed, ToolResult) and listed.ok
    assert listed.data.source_ids == ["fixed-test"]
    assert isinstance(computed, ToolResult) and computed.ok
    assert computed.data.source_id == "fixed-test"
    assert computed.data.scalar == 0.73
    assert computed.data.reward_value == 73.0
    assert computed.data.verdict == "rewarded"
    assert computed.data.signals[0].source_id == "fixed-test"


@pytest.mark.parametrize(
    ("scalar", "verdict"), [(0.0, "no_reward"), (-0.6, "penalized")],
)
def test_zero_and_signed_negative_rewards_remain_distinguishable(
    scalar: float, verdict: str,
) -> None:
    result = _tool(_server(scalar), "learning_compute_reward")(graph_id="g")
    assert result.ok
    assert result.data.source_id == "fixed-test"
    assert result.data.scalar == scalar
    assert result.data.reward_value == 0.0
    assert result.data.verdict == verdict
