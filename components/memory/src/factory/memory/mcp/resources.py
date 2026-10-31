"""MCP resources for memory brick."""

from __future__ import annotations

from typing import Any

from factory.memory.runtime.runtime import MemoryRuntime
from factory.memory.mcp.docs import DOCS


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register MCP resources."""

    @mcp.resource("memory://schemas/config")
    def schema_config() -> dict[str, Any]:
        """JSON schema for memory configuration."""
        from factory.memory.runtime.models import Settings

        return Settings.model_json_schema()

    @mcp.resource("memory://schemas/memory")
    def schema_memory() -> dict[str, Any]:
        """JSON schema for memory object."""
        from factory.memory.runtime.models import Memory

        return Memory.model_json_schema()

    @mcp.resource("memory://docs")
    def docs_list() -> dict[str, Any]:
        """List available documentation."""
        return {"docs": list(DOCS.keys())}

    @mcp.resource("memory://docs/{doc_name}")
    def docs_get(doc_name: str) -> str:
        """Get specific documentation."""
        return DOCS.get(doc_name, f"Documentation '{doc_name}' not found.")

    @mcp.resource("memory://health")
    def health() -> dict[str, Any]:
        """Current health status."""
        return runtime.health_check().model_dump()

    @mcp.resource("memory://backends")
    def backends() -> dict[str, Any]:
        """Available backend adapters."""
        return {
            "available": ["memory", "mem0", "agentcore", "zep", "cognee"],
            "current": runtime.settings.backend,
            "descriptions": {
                "memory": "In-memory volatile storage (testing)",
                "mem0": "Mem0.ai semantic memory",
                "agentcore": "AWS Bedrock AgentCore Memory",
                "zep": "Zep long-term memory with temporal awareness and entity extraction",
                "cognee": "Cognee knowledge-graph-enriched memory with reasoning",
            },
        }
