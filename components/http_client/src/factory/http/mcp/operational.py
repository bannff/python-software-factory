"""Operational typed MCP tools for the HTTP brick."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok

from .contracts import BodyInput, DeleteInput, GetInput, HTTPResponseOutput, JSONBody, RequestInput

if TYPE_CHECKING:
    from ..runtime.runtime import HTTPRuntime


def _response(response: object) -> HTTPResponseOutput:
    return HTTPResponseOutput(status_code=response.status_code, headers=response.headers,
        body=response.text, elapsed_ms=response.elapsed_ms, ok=response.ok)


def _transport_error() -> ToolResult[HTTPResponseOutput]:
    """Do not expose transport exception details through the MCP boundary."""
    return ToolResult(ok=False, data=None, error="http_transport_error")


def register(mcp: Any, get_runtime: Callable[[], "HTTPRuntime"]) -> None:
    """Register stateful HTTP request tools with strict wire validation."""

    @typed_tool(mcp)
    @operational(input_model=GetInput, output_model=HTTPResponseOutput)
    def http_get(url: str, headers: dict[str, str] | None = None,
                 params: dict[str, str] | None = None, timeout: float = 30.0) -> ToolResult[HTTPResponseOutput]:
        """Make an HTTP GET request."""
        request = GetInput.model_validate({"url": url, "headers": headers, "params": params, "timeout": timeout})
        try:
            return ok(_response(get_runtime().get_client().get(**request.model_dump())))
        except Exception:
            return _transport_error()

    @typed_tool(mcp)
    @operational(input_model=BodyInput, output_model=HTTPResponseOutput)
    def http_post(url: str, body: JSONBody | str | None = None,
                  headers: dict[str, str] | None = None, timeout: float = 30.0) -> ToolResult[HTTPResponseOutput]:
        """Make an HTTP POST request."""
        request = BodyInput.model_validate({"url": url, "body": body, "headers": headers, "timeout": timeout})
        try:
            return ok(_response(get_runtime().get_client().post(**request.model_dump())))
        except Exception:
            return _transport_error()

    @typed_tool(mcp)
    @operational(input_model=RequestInput, output_model=HTTPResponseOutput)
    def http_request(method: str, url: str, body: JSONBody | str | None = None,
                     headers: dict[str, str] | None = None, params: dict[str, str] | None = None,
                     timeout: float = 30.0) -> ToolResult[HTTPResponseOutput]:
        """Make an HTTP request with any method."""
        request = RequestInput.model_validate({"method": method, "url": url, "body": body, "headers": headers, "params": params, "timeout": timeout})
        try:
            return ok(_response(get_runtime().get_client().request(**request.model_dump())))
        except Exception:
            return _transport_error()

    @typed_tool(mcp)
    @operational(input_model=BodyInput, output_model=HTTPResponseOutput)
    def http_put(url: str, body: JSONBody | str | None = None,
                 headers: dict[str, str] | None = None, timeout: float = 30.0) -> ToolResult[HTTPResponseOutput]:
        """Make an HTTP PUT request."""
        request = BodyInput.model_validate({"url": url, "body": body, "headers": headers, "timeout": timeout})
        try:
            return ok(_response(get_runtime().get_client().put(**request.model_dump())))
        except Exception:
            return _transport_error()

    @typed_tool(mcp)
    @operational(input_model=DeleteInput, output_model=HTTPResponseOutput)
    def http_delete(url: str, headers: dict[str, str] | None = None,
                    timeout: float = 30.0) -> ToolResult[HTTPResponseOutput]:
        """Make an HTTP DELETE request."""
        request = DeleteInput.model_validate({"url": url, "headers": headers, "timeout": timeout})
        try:
            return ok(_response(get_runtime().get_client().delete(**request.model_dump())))
        except Exception:
            return _transport_error()
