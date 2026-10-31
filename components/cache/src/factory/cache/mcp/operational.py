"""Strict operational MCP tools for the Cache brick."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.decorators import operational
from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.runtime.tool_result import ToolResult, ok
from factory.mcp_utils.runtime.tool_failure import tool_execution_failure

from .contracts.base import EmptyInput
from .contracts.operational import (
    CacheClearOutput, CacheDeleteOutput, CacheExistsOutput, CacheGetOutput,
    CacheKeyInput, CacheKeysInput, CacheKeysOutput, CacheSetInput,
    CacheSetOutput, CacheStatsOutput, CacheTtlOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import CacheRuntime


def register(mcp: Any, get_runtime: Callable[[], "CacheRuntime"]) -> None:
    """Register operational tools with strict Cache-local contracts."""

    @typed_tool(mcp)
    @operational(input_model=CacheKeyInput, output_model=CacheGetOutput)
    def cache_get(key: str) -> ToolResult[CacheGetOutput]:
        """Get a value from cache."""
        request = CacheKeyInput.model_validate({"key": key})
        value = get_runtime().get_cache().get(request.key)
        if value is not None and not isinstance(value, str):
            return tool_execution_failure(cache_get)
        return ok(CacheGetOutput(key=request.key, value=value, found=value is not None))

    @typed_tool(mcp)
    @operational(input_model=CacheSetInput, output_model=CacheSetOutput)
    def cache_set(key: str, value: str, ttl_seconds: int | None = None) -> ToolResult[CacheSetOutput]:
        """Set a value in cache with optional TTL."""
        request = CacheSetInput.model_validate({"key": key, "value": value, "ttl_seconds": ttl_seconds})
        success = get_runtime().get_cache().set(request.key, request.value, request.ttl_seconds)
        return ok(CacheSetOutput(key=request.key, success=success, ttl=request.ttl_seconds))

    @typed_tool(mcp)
    @operational(input_model=CacheKeyInput, output_model=CacheDeleteOutput)
    def cache_delete(key: str) -> ToolResult[CacheDeleteOutput]:
        """Delete a key from cache."""
        request = CacheKeyInput.model_validate({"key": key})
        return ok(CacheDeleteOutput(key=request.key, deleted=get_runtime().get_cache().delete(request.key)))

    @typed_tool(mcp)
    @operational(input_model=CacheKeysInput, output_model=CacheKeysOutput)
    def cache_keys(pattern: str = "*") -> ToolResult[CacheKeysOutput]:
        """List cache keys matching a pattern."""
        request = CacheKeysInput.model_validate({"pattern": pattern})
        keys = get_runtime().get_cache().keys(request.pattern)
        return ok(CacheKeysOutput(pattern=request.pattern, keys=keys, count=len(keys)))

    @typed_tool(mcp)
    @operational(input_model=EmptyInput, output_model=CacheStatsOutput)
    def cache_stats() -> ToolResult[CacheStatsOutput]:
        """Get cache statistics."""
        EmptyInput.model_validate({})
        stats = get_runtime().get_cache().stats()
        return ok(CacheStatsOutput(
            hits=stats.hits, misses=stats.misses, hit_rate=stats.hit_rate,
            size=stats.size, max_size=stats.max_size,
        ))

    @typed_tool(mcp)
    @operational(input_model=EmptyInput, output_model=CacheClearOutput)
    def cache_clear() -> ToolResult[CacheClearOutput]:
        """Clear all cache entries."""
        EmptyInput.model_validate({})
        return ok(CacheClearOutput(cleared=get_runtime().get_cache().clear()))

    @typed_tool(mcp)
    @operational(input_model=CacheKeyInput, output_model=CacheExistsOutput)
    def cache_exists(key: str) -> ToolResult[CacheExistsOutput]:
        """Check if a key exists in cache."""
        request = CacheKeyInput.model_validate({"key": key})
        return ok(CacheExistsOutput(key=request.key, exists=get_runtime().get_cache().exists(request.key)))

    @typed_tool(mcp)
    @operational(input_model=CacheKeyInput, output_model=CacheTtlOutput)
    def cache_ttl(key: str) -> ToolResult[CacheTtlOutput]:
        """Get remaining TTL for a key."""
        request = CacheKeyInput.model_validate({"key": key})
        ttl = get_runtime().get_cache().ttl(request.key)
        return ok(CacheTtlOutput(key=request.key, ttl_seconds=ttl, has_ttl=ttl is not None))
