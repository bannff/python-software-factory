"""Typed MCP boundary tests for the session brick."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from factory.session.server import create_tool_catalog


def _tools():
    return create_tool_catalog().tool_map()


def test_initial_tools_use_typed_deterministic_contracts() -> None:
    tools = _tools()
    expected = {
        "session_get_capabilities",
        "session_health_check",
        "session_describe_config_schema",
    }
    assert expected <= set(tools)
    for name in expected:
        fn = tools[name].fn
        assert getattr(fn, "_mcp_category") == "deterministic"
        assert getattr(fn, "_mcp_input_model") is not None
        assert getattr(fn, "_mcp_output_model") is not None


def test_contract_tools_return_typed_tool_results() -> None:
    tools = _tools()
    result = tools["session_get_capabilities"].fn()
    assert result.ok is True
    assert result.data.name == "session"
    assert "steer_delivery_state" in result.data.features


def test_empty_ingress_rejects_extra_fields() -> None:
    tools = _tools()
    model = getattr(tools["session_health_check"].fn, "_mcp_input_model")
    with pytest.raises(ValidationError):
        model.model_validate({"unexpected": True})
