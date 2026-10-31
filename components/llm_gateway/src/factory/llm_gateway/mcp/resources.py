"""Native MCP resources for the LLM Gateway brick."""
from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Callable


from .docs import LLM_DOCS

if TYPE_CHECKING:
    from ..runtime.runtime import LLMRuntime

_BACKENDS = ["bedrock", "openai", "anthropic", "ollama"]
_EMBEDDING_BACKENDS = ["bedrock", "openai", "ollama"]


def config_schema() -> dict[str, Any]:
    """Return the safe, server-owned public configuration schema."""
    return {
        "type": "object",
        "properties": {
            "backend": {"type": "string", "enum": _BACKENDS},
            "model": {"type": "string", "maxLength": 512},
        },
        "additionalProperties": False,
    }


def response_schema() -> dict[str, Any]:
    """Return the v2 ToolResult envelope schema for operational responses."""
    return {
        "type": "object",
        "required": ["schema_version", "ok", "data", "error", "idempotency_key"],
        "properties": {
            "schema_version": {"const": "v1"},
            "ok": {"type": "boolean"},
            "data": {"type": ["object", "null"]},
            "error": {"type": ["string", "null"]},
            "idempotency_key": {"type": ["string", "null"]},
        },
        "additionalProperties": False,
    }


def safe_health_projection(runtime: "LLMRuntime") -> dict[str, Any]:
    """Return a health projection that never leaks provider exception text."""
    try:
        health = runtime.health_check()
    except Exception:
        return {"providers": {}, "all_healthy": False}
    return {
        "providers": {
            name: {"healthy": status.healthy, "provider": status.provider}
            for name, status in health.items()
        },
        "all_healthy": all(status.healthy for status in health.values()) if health else True,
    }


def register(mcp: Any, get_runtime: Callable[[], "LLMRuntime"]) -> None:
    """Register native static, documentation, and safe live resources."""

    @mcp.resource("llm://schemas/config")
    def resource_config_schema() -> str:
        return json.dumps(config_schema(), indent=2)

    @mcp.resource("llm://schemas/message")
    def resource_message_schema() -> str:
        return json.dumps({
            "type": "object", "additionalProperties": False,
            "required": ["role", "content"],
            "properties": {
                "role": {"enum": ["system", "user", "assistant"]},
                "content": {"type": "string", "minLength": 1, "maxLength": 32768},
            },
        }, indent=2)

    @mcp.resource("llm://schemas/response")
    def resource_response_schema() -> str:
        return json.dumps(response_schema(), indent=2)

    @mcp.resource("llm://docs")
    def resource_docs_list() -> str:
        return json.dumps({"docs": [{"name": key, "title": value["title"]} for key, value in LLM_DOCS.items()]}, indent=2)

    @mcp.resource("llm://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        if doc_name in LLM_DOCS:
            return LLM_DOCS[doc_name]["content"]
        return f"Unknown doc: {doc_name}. Available: {list(LLM_DOCS)}"

    @mcp.resource("llm://backends")
    def resource_backends() -> str:
        return json.dumps({"available": _BACKENDS, "embedding_backends": _EMBEDDING_BACKENDS}, indent=2)

    @mcp.resource("llm://health")
    def resource_health() -> str:
        return json.dumps(safe_health_projection(get_runtime()), indent=2)

    @mcp.resource("llm://factory")
    def resource_factory_ref() -> str:
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": ["foreman_info", "foreman_check", "foreman_guardian_check"],
            "related_bricks": {"kb": "RAG completions", "workflow": "LLM steps", "agents": "agent reasoning"},
        }, indent=2)


__all__ = ["config_schema", "register", "response_schema", "safe_health_projection"]
