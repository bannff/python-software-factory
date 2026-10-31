"""Native MCP resources for the HTTP typed-tool contract."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Callable

from typing import Any

from .docs import HTTP_DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import HTTPRuntime


def register(mcp: Any, get_runtime: Callable[[], "HTTPRuntime"]) -> None:
    """Register schemas, documentation, and runtime observations."""

    @mcp.resource("http://schemas/request")
    def resource_request_schema() -> str:
        return json.dumps({"type": "object", "required": ["method", "url"], "properties": {
            "method": {"type": "string"}, "url": {"type": "string", "format": "uri"},
            "headers": {"type": "object", "additionalProperties": {"type": "string"}},
            "params": {"type": "object", "additionalProperties": {"type": "string"}},
            "body": {"oneOf": [{"type": "object"}, {"type": "string"}, {"type": "null"}]},
            "timeout": {"type": "number", "default": 30.0}}}, indent=2)

    @mcp.resource("http://schemas/response")
    def resource_response_schema() -> str:
        return json.dumps({"type": "object", "required": ["schema_version", "ok", "data", "error"],
            "properties": {"schema_version": {"const": "v1"}, "ok": {"type": "boolean"},
            "data": {"oneOf": [{"type": "object", "required": ["status_code", "headers", "body", "elapsed_ms", "ok"]}, {"type": "null"}]},
            "error": {"type": ["string", "null"]}}}, indent=2)

    @mcp.resource("http://docs/overview")
    def resource_docs_overview() -> str:
        return HTTP_DOCS["overview"]["content"]

    @mcp.resource("http://docs/adapters")
    def resource_docs_adapters() -> str:
        return HTTP_DOCS["adapters"]["content"]

    @mcp.resource("http://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        if doc_name in HTTP_DOCS:
            return HTTP_DOCS[doc_name]["content"]
        return f"Unknown doc: {doc_name}. Available: {list(HTTP_DOCS)}"

    @mcp.resource("http://backends")
    def resource_backends() -> str:
        from ..runtime.runtime import HTTPRuntime
        return json.dumps({"backends": ["httpx", "aiohttp", "tenacity_httpx"],
            "available": HTTPRuntime.available_backends(), "default": "httpx"})

    @mcp.resource("http://stats")
    def resource_stats() -> str:
        health = get_runtime().health_check()
        return json.dumps({"active_clients": len(health), "clients": {
            name: {"healthy": item.healthy, "backend": item.backend,
                   "latency_ms": item.latency_ms} for name, item in health.items()}}, indent=2)

    @mcp.resource("http://factory")
    def resource_factory_ref() -> str:
        return json.dumps({"message": "Use the nine HTTP MCP tools through the factory gateway.",
            "tools": ["http_get_capabilities", "http_health_check", "http_describe_config_schema",
                      "http_list_backends", "http_get", "http_post", "http_request", "http_put", "http_delete"]})
