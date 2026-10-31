"""Neutral brick-catalog aggregator for native MCP v2."""
from __future__ import annotations
import importlib
import logging
from dataclasses import dataclass
from typing import Any

from .tool_dispatch import (
    invoke_catalog_tool, resolve_tool_name, transport_failure, unwrap_transport,
)

logger = logging.getLogger(__name__)

@dataclass
class BrickRegistration:
    name: str
    namespace: str
    tools_count: int
    healthy: bool = True
    error: str | None = None


def _make_failed(name: str, error: str) -> BrickRegistration:
    return BrickRegistration(name, f"factory.{name}", 0, False, error)


class MCPAggregator:
    """Aggregate neutral brick catalogs independently of transport."""
    def __init__(self, server: Any | None = None) -> None:
        self.mcp = server
        self._registered: dict[str, BrickRegistration] = {}
        self._flat_bricks: dict[str, Any] = {}
        self._lazy: Any = None
    def set_available_bricks(self, brick_names: list[str]) -> None:
        from .lazy_loader import LazyBrickLoader
        self._lazy = LazyBrickLoader()
        self._lazy.set_available(brick_names)
        self._registered = self._lazy.registrations
    def get_brick_tools(self, brick_name: str) -> dict[str, Any]:
        return {"error": "Progressive mode not initialized"} if not self._lazy else self._lazy.get_brick_tools(brick_name)
    def _lazy_or_error(self, brick_name: str) -> tuple[Any, str | None]:
        return (None, "Progressive mode not initialized") if not self._lazy else self._lazy._load_or_error(brick_name)
    def get_brick_resources(self, brick_name: str) -> dict[str, Any]:
        from .authorization import is_named_authorized
        if not is_named_authorized(brick_name, f"{brick_name}:resources", "discover", "resource"):
            return {"brick": brick_name, "resources": [], "count": 0}
        from .primitives import get_resources
        catalog, error = self._lazy_or_error(brick_name)
        return {"error": error} if error else get_resources(catalog, brick_name)
    def get_brick_prompts(self, brick_name: str) -> dict[str, Any]:
        from .authorization import is_named_authorized
        if not is_named_authorized(brick_name, f"{brick_name}:prompts", "discover", "prompt"):
            return {"brick": brick_name, "prompts": [], "count": 0}
        from .primitives import get_prompts
        catalog, error = self._lazy_or_error(brick_name)
        return {"error": error} if error else get_prompts(catalog, brick_name)

    async def read_brick_resource(self, brick_name: str, uri: str) -> dict[str, Any]:
        from .authorization import is_named_authorized
        if not is_named_authorized(brick_name, uri, "execute", "resource"):
            return {"error": "authorization_denied"}
        from .primitives import read_resource
        catalog, error = self._lazy_or_error(brick_name)
        return {"error": error} if error else await read_resource(catalog, uri)

    async def render_brick_prompt(
        self, brick_name: str, prompt_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        from .authorization import is_named_authorized
        if not is_named_authorized(brick_name, prompt_name, "execute", "prompt"):
            return {"error": "authorization_denied"}
        from .primitives import render_prompt
        catalog, error = self._lazy_or_error(brick_name)
        return {"error": error} if error else await render_prompt(catalog, prompt_name, arguments)
    def invoke_tool(self, tool_name: str, **kwargs: Any) -> Any:
        if self._lazy is None:
            return {"error": "Aggregator is not initialized"}
        resolution = self.resolve_tool_name(tool_name)
        if not resolution.found:
            return {
                "error": resolution.error,
                "suggestions": list(resolution.suggestions),
            }
        return self._lazy.call_brick_tool_sync(
            resolution.brick_name, resolution.source_name, kwargs or None,
        )

    def invoke_tool_agent(self, tool_name: str, **kwargs: Any) -> Any:
        """Trusted in-process variant of ``invoke_tool`` (agent pool, not proto pool).

        See ``LazyBrickLoader.call_brick_tool_sync_agent`` for why this exists.
        """
        if self._lazy is None:
            return {"error": "Aggregator is not initialized"}
        resolution = self.resolve_tool_name(tool_name)
        if not resolution.found:
            return {
                "error": resolution.error,
                "suggestions": list(resolution.suggestions),
            }
        return self._lazy.call_brick_tool_sync_agent(
            resolution.brick_name, resolution.source_name, kwargs or None,
        )
    def resolve_tool_name(self, tool_name: str, *, public_only: bool = False) -> Any:
        """Resolve through the same canonical names exposed by native MCP v2."""
        from .name_resolution import resolve_tool_request
        return resolve_tool_request(self, tool_name, public_only=public_only)
    def _parse_tool_name(self, tool_name: str) -> tuple[str | None, str | None]:
        """Compatibility projection for callers that need brick/local names."""
        from .name_resolution import parse_tool_name
        return parse_tool_name(self, tool_name)
    def get_brick_tool_map(self, brick_name: str) -> dict[str, Any] | None:
        """Return a brick's neutral tool map from this aggregator."""
        if self._lazy is None:
            catalog = self._flat_bricks.get(brick_name)
            return None if catalog is None else catalog.tool_map()
        catalog, error = self._lazy_or_error(brick_name)
        if error or catalog is None:
            return None
        return self._lazy.get_cached_tool_map(brick_name, catalog)
    def get_brick_tool_names(self, brick_name: str) -> list[str]:
        tools = self.get_brick_tool_map(brick_name) or {}
        from .public_admission import project_public_tools
        projection = project_public_tools(((brick_name, tools),))
        return [item.public_name for item in projection.admitted]
    def get_all_tool_names(self) -> list[str]:
        if self._lazy:
            return self._lazy.get_all_tool_names()
        from .public_admission import project_public_tools
        tool_maps = [(brick, catalog.tool_map())
                     for brick, catalog in self._flat_bricks.items()]
        return [item.public_name for item in project_public_tools(tool_maps).admitted]
    def resolve_brick_tool(
        self, brick_name: str, tool_name: str,
    ) -> tuple[Any | None, str | None, str | None]:
        if self._lazy is None:
            catalog = self._flat_bricks.get(brick_name)
            if catalog is None:
                return None, None, f"Unknown brick '{brick_name}'"
            tools = catalog.tool_map()
        else:
            catalog, error = self._lazy._load_or_error(brick_name)
            if error:
                return None, None, error
            tools = self._lazy.get_cached_tool_map(brick_name, catalog)
        resolved = resolve_tool_name(tools, brick_name, tool_name)
        if resolved is None:
            return None, None, f"Unknown tool '{tool_name}' on '{brick_name}'"
        return catalog, resolved, None

    async def call_public_brick_tool(
        self, brick_name: str, tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Delegate exclusively through the shared admitted public projection."""
        from .public_delegation import call_public_brick_tool
        return await call_public_brick_tool(self, brick_name, tool_name, arguments)

    async def call_brick_tool(
        self, brick_name: str, tool_name: str,
        arguments: dict[str, Any] | None = None, *, task_meta: Any | None = None,
    ) -> dict[str, Any]:
        if self._lazy is not None:
            return await self._lazy.call_brick_tool(
                brick_name, tool_name, arguments, task_meta=task_meta,
            )
        catalog, resolved, error = self.resolve_brick_tool(brick_name, tool_name)
        if error or catalog is None or resolved is None:
            return transport_failure("ToolNotFoundError", error or "Unknown tool")
        return await invoke_catalog_tool(
            catalog.tool_map()[resolved], brick_name, resolved, arguments,
        )
    def register_brick(self, brick_name: str) -> bool:
        try:
            module = importlib.import_module(f"factory.{brick_name}.server")
            namespace = vars(module)
            factory = namespace.get("create_tool_catalog")
            if not callable(factory):
                factory = namespace.get("create_mcp_server")
            catalog = factory() if callable(factory) else None
            if catalog is None or not callable(getattr(catalog, "tool_map", None)):
                raise RuntimeError("brick factory did not return ToolCatalog")
            self._flat_bricks[brick_name] = catalog
            from .lazy_loader import _count_tools
            self._registered[brick_name] = BrickRegistration(
                brick_name, f"factory.{brick_name}", _count_tools(catalog, brick_name), True,
            )
            return True
        except Exception as exc:
            logger.exception("Failed to register '%s'", brick_name)
            self._registered[brick_name] = _make_failed(brick_name, str(exc))
            return False
    def register_all(self, brick_names: list[str]) -> dict[str, bool]:
        return {name: self.register_brick(name) for name in brick_names}
    def get_aggregated_capabilities(self) -> dict[str, Any]:
        return {"server": "factory-aggregator", "version": "1.0.0", "registered_bricks": len(self._registered), "total_tools": sum(item.tools_count for item in self._registered.values()), "bricks": {name: {"namespace": item.namespace, "tools_count": item.tools_count, "healthy": item.healthy} for name, item in self._registered.items()}}
    def get_aggregated_health(self) -> dict[str, Any]:
        healthy = sum(1 for item in self._registered.values() if item.healthy)
        return {"status": "healthy" if healthy == len(self._registered) else "degraded", "healthy_bricks": healthy, "total_bricks": len(self._registered), "bricks": {name: {"healthy": item.healthy, "error": item.error} for name, item in self._registered.items()}}

    aggregated_health_check = get_aggregated_health
    def list_bricks(self) -> dict[str, Any]:
        bricks = [{"name": name, "namespace": item.namespace, "tools_count": item.tools_count, "loaded": item.tools_count >= 0, "healthy": item.healthy, "error": item.error} for name, item in self._registered.items()]
        return {"bricks": bricks, "count": len(bricks), "hint": "tools_count=-1 means not yet loaded. Call get_brick_tools(name) to load."}
    def get_brick_info(self, brick_name: str) -> dict[str, Any]:
        item = self._registered.get(brick_name)
        return {"error": f"Brick '{brick_name}' not registered"} if item is None else {"name": item.name, "namespace": item.namespace, "tools_count": item.tools_count, "healthy": item.healthy, "error": item.error}
    def reload_brick(self, brick_name: str) -> dict[str, Any]:
        try:
            importlib.reload(importlib.import_module(f"factory.{brick_name}.server"))
            if self._lazy:
                self._lazy.invalidate(brick_name)
            return {"success": self.register_brick(brick_name), "brick_name": brick_name}
        except Exception as exc:
            return {"success": False, "error": str(exc)}
