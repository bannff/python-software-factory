"""Focused strict-boundary tests for all public HTTP MCP tools."""
from __future__ import annotations

import asyncio
import inspect
from typing import get_type_hints

import pytest
from mcp.shared.exceptions import MCPError
from pydantic import ValidationError

from factory.http.mcp.contracts import BodyInput, GetInput, HTTPResponseOutput, StrictModel
from factory.http.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult

TOOL_NAMES = {
    "http_get_capabilities", "http_health_check", "http_describe_config_schema",
    "http_list_backends", "http_get", "http_post", "http_request", "http_put", "http_delete",
}


class Response:
    status_code = 404
    headers = {"content-type": "text/plain"}
    text = "not found"
    elapsed_ms = 4.0
    ok = False


class Client:
    def get(self, **kwargs): return Response()
    def post(self, **kwargs): return Response()
    def request(self, **kwargs): return Response()
    def put(self, **kwargs): return Response()
    def delete(self, **kwargs): return Response()


class Runtime:
    backend_name = "fake"
    def get_client(self): return Client()
    def health_check(self): return {}


def _tool(name: str):
    return asyncio.run(create_mcp_server(Runtime()).get_tool(name))


def test_catalog_has_exactly_nine_http_tools() -> None:
    mcp = create_mcp_server(Runtime())
    tools = {tool.name for tool in asyncio.run(mcp.list_tools())}
    assert tools == TOOL_NAMES


@pytest.mark.parametrize("name", sorted(TOOL_NAMES))
def test_public_tools_have_exact_typed_envelopes(name: str) -> None:
    tool = _tool(name)
    hints = get_type_hints(tool.fn)
    assert hints["return"] == ToolResult[tool.fn._mcp_output_model]
    assert issubclass(tool.fn._mcp_input_model, StrictModel)
    assert tool.fn._mcp_input_model.model_config["extra"] == "forbid"
    assert tool.fn._mcp_input_model.model_config["strict"] is True


@pytest.mark.parametrize("tool_name,kwargs", [
    ("http_get", {"url": "https://example.test"}),
    ("http_post", {"url": "https://example.test", "body": {"key": "value"}}),
    ("http_request", {"method": "PATCH", "url": "https://example.test"}),
    ("http_request", {"method": "HEAD", "url": "https://example.test"}),
    ("http_request", {"method": "OPTIONS", "url": "https://example.test"}),
    ("http_put", {"url": "https://example.test", "body": "value"}),
    ("http_delete", {"url": "https://example.test"}),
])
def test_http_verbs_keep_4xx_as_successful_typed_data(tool_name: str, kwargs: dict[str, object]) -> None:
    result = _tool(tool_name).fn(**kwargs)
    assert result.ok is True
    assert isinstance(result.data, HTTPResponseOutput)
    assert result.data.status_code == 404
    assert result.data.ok is False


def test_models_reject_extra_and_coerced_timeout() -> None:
    with pytest.raises(ValidationError):
        GetInput.model_validate({"url": "https://example.test", "timeout": "30"})
    with pytest.raises(ValidationError):
        GetInput.model_validate({"url": "https://example.test", "extra": "no"})
    assert BodyInput.model_validate({"url": "https://example.test", "body": {"n": 1}}).body == {"n": 1}


@pytest.mark.parametrize(("tool_name", "arguments"), [
    ("http_get", {"url": "https://example.test", "timeout": "30"}),
    ("http_post", {"url": "https://example.test", "timeout": "30"}),
    ("http_request", {"method": "PATCH", "url": "https://example.test", "timeout": "30"}),
    ("http_put", {"url": "https://example.test", "timeout": "30"}),
    ("http_delete", {"url": "https://example.test", "unexpected": "value"}),
    ("http_get_capabilities", {"unexpected": "value"}),
    ("http_health_check", {"unexpected": "value"}),
    ("http_describe_config_schema", {"unexpected": "value"}),
    ("http_list_backends", {"unexpected": "value"}),
])
def test_raw_transport_preserves_strict_invalid_arguments(
    tool_name: str, arguments: dict[str, object],
) -> None:
    with pytest.raises(MCPError):
        asyncio.run(_tool(tool_name).run(arguments))


def test_transport_failure_is_generic_and_secret_safe() -> None:
    class BrokenClient:
        def get(self, **kwargs): raise RuntimeError("token=super-secret https://internal")
    class BrokenRuntime(Runtime):
        def get_client(self): return BrokenClient()
    result = asyncio.run(create_mcp_server(BrokenRuntime()).get_tool("http_get")).fn(url="https://example.test")
    assert result.ok is False
    assert result.error == "http_transport_error"
    assert "secret" not in result.error


def test_resources_and_prompts_describe_envelopes_and_dispatch() -> None:
    from factory.http.mcp.docs import HTTP_DOCS
    from factory.http.mcp.templates import PROMPT_TEMPLATES
    assert "ToolResult" in HTTP_DOCS["overview"]["content"]
    assert all(name in HTTP_DOCS["overview"]["content"] for name in TOOL_NAMES)
    prompt = PROMPT_TEMPLATES["make_request"]["template"].format(
        method="PATCH", method_lower="patch", url="https://example.test", purpose="test")
    assert "http_request" in prompt and "http_patch" not in prompt
