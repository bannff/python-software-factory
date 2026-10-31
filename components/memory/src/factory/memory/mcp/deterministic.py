"""Category-neutral typed MCP contract and read tools for Memory."""
from __future__ import annotations

from typing import Any
from factory.mcp_utils.context import get_principal_id
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.mcp_utils.typed import typed

from factory.memory.runtime.runtime import MemoryRuntime

from .contracts.base import EmptyInput
from .contracts.deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, EmbeddingStatusOutput, HealthOutput,
    MemoryGetOutput, MemoryHistoryOutput, MemoryIdInput, MemoryListInput,
    MemoryListOutput, MemoryStatsInput, MemoryStatsOutput, RecallPathOutput,
)
from .contracts.operational import MemoryBulkFilterInput, MemoryBulkPreviewOutput

_ERROR = "user_id required: pass explicitly or authenticate via Bearer token"


def _user_id(user_id: str | None) -> str | None:
    return user_id if user_id is not None else get_principal_id()


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register category-neutral Memory tools without changing live categories."""

    @mcp.tool()
    @typed(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return {
            "name": "memory", "version": "1.0.0",
            "features": ["semantic_memory", "short_term_memory", "long_term_memory", "memory_consolidation", "relevance_scoring"],
            "adapters": ["memory", "mem0", "agentcore", "zep", "cognee"],
            "mcp_contract": {"tools": ["get_capabilities", "health_check", "describe_config_schema"], "resources": True, "prompts": True},
        }

    @mcp.tool()
    @typed(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        return runtime.health_check().model_dump(mode="json")

    @mcp.tool()
    @typed(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        from factory.memory.runtime.models import Settings
        return {"config_schema": Settings.model_json_schema()}

    @mcp.tool()
    @typed(input_model=MemoryIdInput, output_model=MemoryGetOutput)
    def memory_get(memory_id: str) -> ToolResult[MemoryGetOutput]:
        memory = runtime.get(memory_id)
        return {"memory_id": memory_id, "found": memory is not None,
                "memory": memory.model_dump(mode="json") if memory else None}

    @mcp.tool()
    @typed(input_model=MemoryIdInput, output_model=RecallPathOutput)
    def memory_recall_inspect(memory_id: str) -> ToolResult[RecallPathOutput]:
        """Row 45's recall inspection (owner direction 2026-09-16): the
        real owner/chain/similarity edges around one memory, as an
        owner-facing "why did this surface" trace. ``supported=False``
        (not an error) on adapters with no graph substrate to inspect."""
        path = runtime.recall_path(memory_id)
        if path is None:
            return {"memory_id": memory_id, "supported": False}
        return {
            "memory_id": memory_id, "supported": True,
            "owner_id": path["owner_id"],
            "followed": path["followed"].model_dump(mode="json") if path["followed"] else None,
            "similar": [
                {"memory": item["memory"].model_dump(mode="json"), "score": item["score"]}
                for item in path["similar"]
            ],
        }

    @mcp.tool()
    @typed(input_model=MemoryIdInput, output_model=MemoryHistoryOutput)
    def memory_history(memory_id: str) -> ToolResult[MemoryHistoryOutput]:
        """Row 47 (Replaced experiences) — every version of the chain
        containing ``memory_id``, newest first. Informational only: no
        restore action exists (owner ruling — the curator, not a user,
        replaces memories). ``supported=False`` (not an error) on
        adapters with no supersession substrate to inspect."""
        versions = runtime.history(memory_id)
        if versions is None:
            return {"memory_id": memory_id, "supported": False}
        return {
            "memory_id": memory_id, "supported": True,
            "versions": [v.model_dump(mode="json") for v in versions],
        }

    @mcp.tool()
    @typed(input_model=MemoryListInput, output_model=MemoryListOutput)
    def memory_list(user_id: str | None = None, limit: int = 100, metadata: dict[str, str] | None = None) -> ToolResult[MemoryListOutput]:
        resolved = _user_id(user_id)
        if resolved is None:
            return {"user_id": "", "memories": [], "count": 0, "error": _ERROR}
        memories = runtime.list_all(resolved, limit, metadata=metadata)
        return {"user_id": resolved, "memories": [m.model_dump(mode="json") for m in memories], "count": len(memories)}

    @mcp.tool()
    @typed(input_model=MemoryBulkFilterInput, output_model=MemoryBulkPreviewOutput)
    def memory_bulk_preview(
        user_id: str | None = None, query: str | None = None,
        memory_type: str | None = None, metadata: dict[str, str] | None = None,
        limit: int = 1000,
    ) -> ToolResult[MemoryBulkPreviewOutput]:
        """Row 43 bulk correction (owner ruling: bulk delete of matched
        memories only) — the preview half. Uses the SAME
        ``MemoryRuntime.bulk_match`` filter ``memory_bulk_delete`` applies,
        so the count shown here is never an estimate a real delete could
        contradict."""
        resolved = _user_id(user_id)
        if resolved is None:
            return {"user_id": None, "matched_count": 0, "sample": [], "error": _ERROR}
        matched = runtime.bulk_match(resolved, query, memory_type=memory_type, metadata=metadata, limit=limit)
        return {
            "user_id": resolved, "matched_count": len(matched),
            "sample": [m.model_dump(mode="json") for m in matched[:20]],
        }

    @mcp.tool()
    @typed(input_model=MemoryStatsInput, output_model=MemoryStatsOutput)
    def memory_stats(user_id: str | None = None) -> ToolResult[MemoryStatsOutput]:
        """Stats for the caller's own memories by default.

        Mirrors ``memory_list``'s ambient-identity resolution (Gate A.5
        `6edab2de`): an omitted ``user_id`` now scopes to the caller's own
        principal instead of silently aggregating across every user. Pass
        an explicit ``user_id`` for the (pre-existing, unchanged) global
        aggregate — same trust boundary as every other tool in this file.
        """
        return runtime.stats(_user_id(user_id)).model_dump(mode="json")

    @mcp.tool()
    @typed(input_model=EmptyInput, output_model=EmbeddingStatusOutput)
    def memory_get_embedding_status() -> ToolResult[EmbeddingStatusOutput]:
        """Row 50 (Embeddings) — honest status, no live enable/disable.

        Backend + embedder are both resolved once at process start via
        ``MEMORY_BACKEND``/``MEMORY_LOCAL_EMBED_MODEL`` (mirrors
        ``browser.get_engine_status``'s pattern for the same reason: this
        brick has no live toggle, only a config-time choice + restart).
        """
        store = runtime.adapter
        embedder = getattr(store, "embedder", None)
        is_graph = embedder is not None
        return {
            "backend": "graph" if is_graph else type(store).__name__,
            "is_graph_backend": is_graph,
            "embedder_configured": is_graph,
            "is_semantic": bool(is_graph and embedder.is_semantic),
            "load_error": embedder.load_error if is_graph else "not_graph_backend",
            "model_path": embedder.model_path if is_graph else "",
            "dimensions": embedder.dimensions if is_graph else 0,
            "change_hint": (
                "Set MEMORY_BACKEND=graph and MEMORY_LOCAL_EMBED_MODEL="
                "/path/to/model.gguf in the API environment and restart."
            ),
        }
