"""Category-neutral typed stateful MCP tools for Memory."""
from __future__ import annotations

from typing import Any

from pydantic import JsonValue
from factory.mcp_utils.context import get_principal_id
from factory.mcp_utils.interface import get_service, validate_protected_persistence
from factory.mcp_utils.runtime.tool_result import ToolResult
from factory.mcp_utils.typed import typed

from factory.memory.core import MemoryCategory
from factory.memory.runtime.idempotency import MemoryIdempotencyError, store_once
from factory.memory.runtime.runtime import MemoryRuntime

from .contracts.deterministic import MemoryIdInput
from .contracts.operational import (
    ConsolidateOutput, DeleteUserOutput, MemoryBulkDeleteOutput,
    MemoryBulkFilterInput, MemoryDeleteOutput, MemoryEvolveInput,
    MemoryEvolveOutput, MemoryRetrieveInput, MemoryRetrieveOutput,
    MemoryStoreInput, MemoryStoreOutput, MemoryUpdateInput, MemoryUpdateOutput,
    UserInput,
)

_VALID_CATEGORIES = {item.value for item in MemoryCategory}
_ERROR = "user_id required: pass explicitly or authenticate via Bearer token"


def _user_id(user_id: str | None) -> str | None:
    return user_id if user_id is not None else get_principal_id()


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register category-neutral tools without changing live categories."""

    @mcp.tool()
    @typed(input_model=MemoryStoreInput, output_model=MemoryStoreOutput)
    def memory_store(content: str, user_id: str | None = None, memory_type: str = "short_term", category: str = "custom", metadata: dict[str, JsonValue] | None = None, ttl_seconds: int | None = None, idempotency_key: str | None = None) -> ToolResult[MemoryStoreOutput]:
        if category not in _VALID_CATEGORIES:
            return {"stored": False, "error": f"Invalid category '{category}'. Must be one of: {sorted(_VALID_CATEGORIES)}"}
        resolved = _user_id(user_id)
        if resolved is None:
            return {"stored": False, "error": _ERROR}
        try:
            validate_protected_persistence({
                "content": content, "metadata": metadata or {},
            })
        except ValueError:
            return {
                "stored": False,
                "error": "protected content requires an approved projection",
            }
        try:
            if idempotency_key:
                invoker = get_service("tool_invoker")
                if not callable(invoker):
                    return {
                        "stored": False,
                        "error": "memory idempotency store unavailable",
                    }
                memory = store_once(
                    runtime, invoker, idempotency_key=idempotency_key,
                    user_id=resolved, content=content, memory_type=memory_type,
                    category=category, metadata=metadata,
                    ttl_seconds=ttl_seconds,
                )
            else:
                memory = runtime.store(
                    user_id=resolved, content=content, memory_type=memory_type,
                    category=category, metadata=metadata,
                    ttl_seconds=ttl_seconds,
                )
        except ValueError:
            return {"stored": False, "error": "memory idempotency conflict"}
        except MemoryIdempotencyError as exc:
            return {"stored": False, "error": str(exc)}
        return {"stored": True, "memory": memory.model_dump(mode="json")}

    @mcp.tool()
    @typed(input_model=MemoryRetrieveInput, output_model=MemoryRetrieveOutput)
    def memory_retrieve(query: str, user_id: str | None = None, memory_type: str | None = None, category: str | None = None, min_relevance: float = 0.3, limit: int = 5, tags: list[str] | None = None, metadata: dict[str, str] | None = None) -> ToolResult[MemoryRetrieveOutput]:
        resolved = _user_id(user_id)
        if resolved is None:
            return {"error": _ERROR}
        memories = runtime.retrieve(user_id=resolved, query=query, memory_type=memory_type, category=category, min_relevance=min_relevance, limit=limit, tags=tags, metadata=metadata)
        items = [memory.model_dump(mode="json") for memory in memories]
        return {"memories": items, "count": len(items)}

    @mcp.tool()
    @typed(input_model=MemoryIdInput, output_model=MemoryDeleteOutput)
    def memory_delete(memory_id: str) -> ToolResult[MemoryDeleteOutput]:
        return {"memory_id": memory_id, "deleted": runtime.delete(memory_id)}

    @mcp.tool()
    @typed(input_model=MemoryBulkFilterInput, output_model=MemoryBulkDeleteOutput)
    def memory_bulk_delete(
        user_id: str | None = None, query: str | None = None,
        memory_type: str | None = None, metadata: dict[str, JsonValue] | None = None,
        limit: int = 1000,
    ) -> ToolResult[MemoryBulkDeleteOutput]:
        """Row 43 bulk correction (owner ruling: bulk delete of matched
        memories only, no bulk content edit) — the apply half of
        ``memory_bulk_preview``, same filter shape and same match logic
        via ``MemoryRuntime.bulk_delete`` so a delete can never remove a
        different set than what the preview showed."""
        resolved = _user_id(user_id)
        if resolved is None:
            return {"user_id": None, "deleted_count": 0, "deleted_ids": [], "error": _ERROR}
        metadata_str = {k: str(v) for k, v in (metadata or {}).items()} or None
        deleted_ids = runtime.bulk_delete(
            resolved, query, memory_type=memory_type, metadata=metadata_str, limit=limit,
        )
        return {"user_id": resolved, "deleted_count": len(deleted_ids), "deleted_ids": deleted_ids}

    @mcp.tool()
    @typed(input_model=MemoryUpdateInput, output_model=MemoryUpdateOutput)
    def memory_update(memory_id: str, content: str) -> ToolResult[MemoryUpdateOutput]:
        try:
            validate_protected_persistence({"content": content})
        except ValueError:
            return {
                "memory_id": memory_id, "updated": False,
                "error": "protected content requires an approved projection",
            }
        memory = runtime.update(memory_id, content)
        if memory is None:
            existing = runtime.get(memory_id)
            error = (
                "memory update is not supported on the active backend"
                if existing is not None else "memory not found"
            )
            return {"memory_id": memory_id, "updated": False, "error": error}
        return {
            "memory_id": memory_id, "updated": True,
            "memory": memory.model_dump(mode="json"),
        }

    @mcp.tool()
    @typed(input_model=UserInput, output_model=DeleteUserOutput)
    def memory_delete_user(user_id: str | None = None) -> ToolResult[DeleteUserOutput]:
        resolved = _user_id(user_id)
        if resolved is None:
            return {"error": _ERROR}
        return {"user_id": resolved, "deleted_count": runtime.delete_user_memories(resolved)}

    @mcp.tool()
    @typed(input_model=UserInput, output_model=ConsolidateOutput)
    def memory_consolidate(user_id: str | None = None) -> ToolResult[ConsolidateOutput]:
        resolved = _user_id(user_id)
        if resolved is None:
            return {"error": _ERROR}
        return {"user_id": resolved, "consolidated_count": runtime.consolidate(resolved)}

    @mcp.tool()
    @typed(input_model=MemoryEvolveInput, output_model=MemoryEvolveOutput)
    def memory_evolve(user_id: str | None = None, memory_ids: list[str] | None = None) -> ToolResult[MemoryEvolveOutput]:
        resolved = _user_id(user_id)
        if resolved is None:
            return {"error": _ERROR}
        from factory.memory.runtime.evolve_runner import run_evolve
        return run_evolve(runtime, resolved, memory_ids)
