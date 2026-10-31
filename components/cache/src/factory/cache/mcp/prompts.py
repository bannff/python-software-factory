"""MCP Prompt registration for Cache brick.

Prompts provide guided workflows for common tasks:
- Configuring cache backends
- Debugging cache issues
- Optimizing cache performance
"""

from __future__ import annotations

from typing import Any, TYPE_CHECKING, Callable

from .templates import PROMPT_TEMPLATES, BACKEND_GUIDES

if TYPE_CHECKING:
    from ..runtime.runtime import CacheRuntime


def register(mcp: Any, get_runtime: Callable[[], "CacheRuntime"]) -> None:
    """Register all Cache prompts with the MCP server."""

    @mcp.prompt()
    def configure_cache(backend: str = "memory") -> str:
        """Generate guidance for setting up a cache backend."""
        backend = backend.lower()
        if backend not in BACKEND_GUIDES:
            backend = "memory"

        guide = BACKEND_GUIDES[backend]
        runtime = get_runtime()
        health = runtime.health_check()

        current_config = "No active caches" if not health else f"Active caches: {len(health)}"

        return PROMPT_TEMPLATES["configure_cache"]["template"].format(
            backend=backend,
            current_config=current_config,
            setup_guide=guide["setup_guide"],
            config_params=guide["config_params"],
        )

    @mcp.prompt()
    def debug_cache(key: str = "", issue: str = "") -> str:
        """Generate guidance for debugging cache issues."""
        return PROMPT_TEMPLATES["debug_cache"]["template"].format(
            key=key or "your:key",
            pattern=key.rsplit(":", 1)[0] + ":*" if ":" in key else "*",
            issue=issue or "Cache not behaving as expected",
        )

    @mcp.prompt()
    def optimize_cache() -> str:
        """Generate guidance for cache optimization."""
        runtime = get_runtime()
        cache = runtime.get_cache()
        stats = cache.stats()

        # Analyze hit rate
        if stats.hit_rate >= 0.8:
            hit_rate_analysis = "✅ Excellent hit rate. Cache is well-utilized."
        elif stats.hit_rate >= 0.5:
            hit_rate_analysis = "⚠️ Moderate hit rate. Consider TTL adjustments."
        else:
            hit_rate_analysis = "❌ Low hit rate. Review caching strategy."

        # Analyze size
        if stats.max_size and stats.size >= stats.max_size * 0.9:
            size_analysis = "⚠️ Cache near capacity. Consider increasing max_size."
        else:
            size_analysis = "✅ Cache size is healthy."

        return PROMPT_TEMPLATES["optimize_cache"]["template"].format(
            current_stats=f"Hits: {stats.hits}, Misses: {stats.misses}",
            hit_rate=f"{stats.hit_rate:.1%}",
            hit_rate_analysis=hit_rate_analysis,
            size=stats.size,
            max_size=stats.max_size or "unlimited",
            size_analysis=size_analysis,
            ttl_recommendations="| Session | - | 3600s |\n| Config | - | 60s |",
            size_recommendations="Consider max_size based on memory constraints.",
            backend_recommendations="Use Redis for distributed deployments.",
        )
