"""Full-server typed-boundary coverage for the Oracle MCP surface."""
from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import pytest

from factory.graph.mcp.core_models import EntityData, EntityLookupData, FindingStateData
from mcp.shared.exceptions import MCPError
from factory.mcp_utils.interface import SchemaMigrationError, ToolResult, get_service, ok, set_service
from factory.oracle.interface import create_server, register_verifier, reset_registry
from factory.oracle.runtime.runtime import reset_runtime


DETERMINISTIC = {
    "oracle_get_capabilities", "oracle_health_check", "oracle_describe_config_schema",
    "oracle_list_verifiers", "oracle_list_states",
}
OPERATIONAL = {"oracle_verify_finding"}


def _server():
    return create_server()


def _tool(name: str):
    return asyncio.run(_server().get_tool(name))


def _wire(tool: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    return json.loads(asyncio.run(tool.run(arguments)).content[0].text)


class _Verifier:
    name = "registered"

    def __init__(self, state: str) -> None:
        self._state = state

    def verify(self, finding: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
        return {"state": self._state, "evidence": "stub", "verifier": self.name}


class _RaisingVerifier:
    name = "raising"

    def verify(self, finding: dict[str, Any], context: dict[str, Any]) -> dict[str, str]:
        raise RuntimeError("boom")


def _graph_invoker(calls: list[tuple[str, dict[str, Any]]]):
    def invoke(tool_name: str, **kwargs: Any) -> ToolResult[Any]:
        calls.append((tool_name, kwargs))
        if tool_name == "graph_graph_get_entity":
            return ok(EntityLookupData(found=True, entity_id=kwargs["entity_id"], entity=EntityData(
                id=kwargs["entity_id"], type="Finding",
                properties={"state": "candidate"},
            )))
        assert tool_name == "graph_graph_set_finding_state"
        return ok(FindingStateData(success=True, finding_id=kwargs["finding_id"], state=kwargs["state"]))
    return invoke


def _verify(domain: str, backend: str = "") -> tuple[dict[str, Any], list[tuple[str, dict[str, Any]]]]:
    calls: list[tuple[str, dict[str, Any]]] = []
    previous = get_service("tool_invoker")
    try:
        set_service("tool_invoker", _graph_invoker(calls))
        return _wire(_tool("oracle_verify_finding"), {
            "finding_id": "f-1", "domain": domain, "backend": backend,
        }), calls
    finally:
        set_service("tool_invoker", previous)
        reset_registry()
        reset_runtime()


def test_fresh_server_has_exact_strict_typed_catalog() -> None:
    tools = {tool.name: tool for tool in asyncio.run(_server().list_tools())}
    assert set(tools) == DETERMINISTIC | OPERATIONAL
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "deterministic"} == DETERMINISTIC
    assert {name for name, tool in tools.items() if tool.fn._mcp_category == "operational"} == OPERATIONAL
    for tool in tools.values():
        input_model, output_model = tool.fn._mcp_input_model, tool.fn._mcp_output_model
        assert input_model.__module__ == output_model.__module__ == "factory.oracle.mcp.contracts"
        assert input_model.model_config.get("extra") == "forbid" and input_model.model_config.get("strict") is True
        assert output_model.model_config.get("extra") == "forbid" and output_model.model_config.get("strict") is True
        assert str(inspect.signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_raw_transport_rejects_numeric_and_extra_arguments() -> None:
    verify = _tool("oracle_verify_finding")
    assert list(inspect.signature(verify.fn).parameters) == ["finding_id", "domain", "backend"]
    with pytest.raises(MCPError, match="Invalid arguments"):
        asyncio.run(verify.run({"finding_id": 1}))
    with pytest.raises(MCPError, match="Invalid arguments"):
        asyncio.run(verify.run({"finding_id": "f", "unexpected": True}))
    with pytest.raises(MCPError, match="Invalid arguments"):
        asyncio.run(_tool("oracle_list_states").run({"unexpected": True}))
    with pytest.raises(SchemaMigrationError):
        verify.fn(finding_id=1)


def test_raw_transport_preserves_envelope_and_schema_alias() -> None:
    wire = _wire(_tool("oracle_describe_config_schema"), {})
    assert wire == {"schema_version": "v1", "ok": True, "data": {
        "type": "object", "additionalProperties": False, "properties": {},
    }, "error": None, "idempotency_key": None}


def test_registered_verifier_forwards_nondefault_backend_to_graph_read_and_write() -> None:
    reset_registry()
    register_verifier("custom", _Verifier("verified"))
    wire, calls = _verify("custom", backend="networkx")
    assert wire["ok"] and wire["data"] == {
        "success": True, "finding_id": "f-1", "persisted": True, "state": "verified",
        "evidence": "stub", "verifier": "registered", "error": None,
    }
    assert [(name, kwargs["backend"]) for name, kwargs in calls] == [
        ("graph_graph_get_entity", "networkx"), ("graph_graph_set_finding_state", "networkx"),
    ]


def test_raising_verifier_is_successful_and_persists_neutral_state_over_mcp() -> None:
    reset_registry()
    register_verifier("custom", _RaisingVerifier())
    wire, calls = _verify("custom")
    assert wire["ok"] and wire["data"]["success"] and wire["data"]["persisted"]
    assert wire["data"]["state"] == "candidate" and "verifier error: boom" in wire["data"]["evidence"]
    assert calls[-1] == ("graph_graph_set_finding_state", {"finding_id": "f-1", "state": "candidate", "backend": ""})


def test_invalid_verifier_state_is_successful_but_never_written() -> None:
    reset_registry()
    register_verifier("custom", _Verifier("invalid"))
    wire, calls = _verify("custom")
    assert wire["ok"] and wire["data"]["success"] and wire["data"]["persisted"] is False
    assert wire["data"]["state"] == "invalid" and [name for name, _ in calls] == ["graph_graph_get_entity"]


def test_resources_and_prompts_remain_native_protocol_surfaces() -> None:
    server = _server()
    resources = {str(item.uri) for item in asyncio.run(server.list_resources())}
    assert resources == {"oracle://schemas/verify-result", "oracle://docs/oracle"}
    schema = json.loads(asyncio.run(server.read_resource("oracle://schemas/verify-result")).contents[0].content)
    docs = asyncio.run(server.read_resource("oracle://docs/oracle")).contents[0].content
    assert schema["required"] == ["state", "verifier"] and schema["properties"]["state"]["enum"] == ["candidate", "verifying", "verified", "refuted"]
    assert "domain-agnostic verification oracle" in docs
    default = asyncio.run(server.render_prompt("verify_finding", {"finding_id": "f-1"})).messages[0].content.text
    explicit = asyncio.run(server.render_prompt("verify_finding", {"finding_id": "f-1", "domain": "wine"})).messages[0].content.text
    assert "for domain" not in default and "domain='wine'" in explicit
