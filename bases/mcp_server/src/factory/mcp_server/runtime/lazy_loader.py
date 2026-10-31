"""Lazy loading, discovery, and invocation of neutral brick catalogs."""
from __future__ import annotations

import importlib
import logging
import os
from typing import Any

from .aggregator import BrickRegistration, _make_failed
from .tool_dispatch import (
    invoke_catalog_tool, resolve_tool_name, transport_failure, unwrap_transport,
)

logger = logging.getLogger(__name__)


def _public_not_found() -> dict[str, Any]:
    return transport_failure("ToolNotFoundError", "tool_not_found")


def _get_tool_map(catalog: Any) -> dict[str, Any]:
    tool_map = getattr(catalog, "tool_map", None)
    if not callable(tool_map):
        raise TypeError("brick factory must return ToolCatalog")
    return tool_map()


def _count_tools(catalog: Any, brick_name: str = "unknown") -> int:
    from .public_admission import project_public_tools
    projection = project_public_tools(((brick_name, _get_tool_map(catalog)),))
    return len(projection.admitted)


class LazyBrickLoader:
    def __init__(self) -> None:
        self._cache: dict[str, Any] = {}
        self._tool_cache: dict[str, dict[str, Any]] = {}
        self._available: list[str] = []
        self._registrations: dict[str, BrickRegistration] = {}

    @property
    def available_bricks(self) -> list[str]:
        return list(self._available)

    @property
    def registrations(self) -> dict[str, BrickRegistration]:
        return self._registrations

    def set_available(self, brick_names: list[str]) -> None:
        self._available = list(brick_names)
        for name in brick_names:
            self._registrations.setdefault(
                name, BrickRegistration(name, f"factory.{name}", -1, True),
            )
        if os.environ.get("EAGER_LOAD", "").strip() in ("1", "true", "yes"):
            for name in self._available:
                self.ensure_loaded(name)

    def ensure_loaded(self, brick_name: str) -> Any | None:
        if brick_name in self._cache:
            return self._cache[brick_name]
        try:
            module = importlib.import_module(f"factory.{brick_name}.server")
            namespace = vars(module)
            factory = namespace.get("create_tool_catalog")
            if not callable(factory):
                factory = namespace.get("create_mcp_server")
            catalog = factory() if callable(factory) else namespace.get("mcp")
            if catalog is None:
                raise RuntimeError("No create_tool_catalog() or create_mcp_server()")
            _get_tool_map(catalog)
            self._cache[brick_name] = catalog
            count = _count_tools(catalog, brick_name)
            self._registrations[brick_name] = BrickRegistration(
                brick_name, f"factory.{brick_name}", count, True,
            )
            return catalog
        except Exception as exc:
            logger.exception("Failed to lazy-load '%s'", brick_name)
            self._registrations[brick_name] = _make_failed(brick_name, str(exc))
            return None

    def invalidate(self, brick_name: str) -> None:
        self._cache.pop(brick_name, None)
        self._tool_cache.pop(brick_name, None)

    def _is_known(self, brick_name: str) -> bool:
        return brick_name in self._available or brick_name in self._registrations

    def _load_or_error(self, brick_name: str) -> tuple[Any | None, str | None]:
        if not self._is_known(brick_name):
            return None, f"Unknown brick: '{brick_name}'"
        catalog = self.ensure_loaded(brick_name)
        if catalog is None:
            registration = self._registrations.get(brick_name)
            return None, f"Failed to load brick '{brick_name}': {registration.error if registration else '?'}"
        return catalog, None

    def get_cached_tool_map(self, brick_name: str, catalog: Any) -> dict[str, Any]:
        if brick_name not in self._tool_cache:
            self._tool_cache[brick_name] = _get_tool_map(catalog)
        return self._tool_cache[brick_name]

    def get_brick_tools(self, brick_name: str) -> dict[str, Any]:
        catalog, error = self._load_or_error(brick_name)
        if error:
            return {"error": error}
        from .public_admission import project_public_tools
        from .tool_catalog import tool_schema_entry
        projection = project_public_tools(((
            brick_name, self.get_cached_tool_map(brick_name, catalog),
        ),))
        from .authorization import filter_projection
        admitted = filter_projection(projection)
        schemas = [
            tool_schema_entry(item.source_name, item.tool, item.input_schema)
            for item in admitted
        ]
        return {
            "brick": brick_name, "tools": schemas, "count": len(schemas),
            "invalid_tools": list(projection.invalid_tools),
        }

    async def call_public_brick_tool(
        self, brick_name: str, tool_name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Invoke only through the brick's admitted public projection."""
        catalog, error = self._load_or_error(brick_name)
        if error or catalog is None:
            return _public_not_found()
        from .public_admission import project_public_tools
        projection = project_public_tools(((
            brick_name, self.get_cached_tool_map(brick_name, catalog),
        ),))
        admitted = {item.source_name: item for item in projection.admitted}
        resolved = resolve_tool_name(
            {name: item.tool for name, item in admitted.items()}, brick_name, tool_name,
        )
        if resolved is None:
            return _public_not_found()
        from .authorization import is_authorized, trusted_arguments
        item = admitted[resolved]
        trusted = trusted_arguments(item.tool, arguments)
        if trusted is None or not is_authorized(item, "execute"):
            return transport_failure("AuthorizationError", "authorization_denied")
        return await invoke_catalog_tool(
            item.tool, brick_name, resolved, trusted,
        )

    async def call_brick_tool(
        self, brick_name: str, tool_name: str,
        arguments: dict[str, Any] | None = None, *, task_meta: Any | None = None,
    ) -> dict[str, Any]:
        del task_meta
        catalog, error = self._load_or_error(brick_name)
        if error:
            return transport_failure("BrickLoadError", error)
        tools = self.get_cached_tool_map(brick_name, catalog)
        resolved = resolve_tool_name(tools, brick_name, tool_name)
        if resolved is None:
            return transport_failure("ToolNotFoundError", f"Unknown tool '{tool_name}' on '{brick_name}'")
        return await invoke_catalog_tool(
            tools[resolved], brick_name, resolved, arguments,
        )

    def call_brick_tool_sync(
        self, brick_name: str, tool_name: str, arguments: dict[str, Any] | None = None,
        *, task_meta: Any | None = None,
    ) -> Any:
        from .pools import _run_sync
        return unwrap_transport(_run_sync(self.call_brick_tool(
            brick_name, tool_name, arguments, task_meta=task_meta,
        )))

    def call_brick_tool_sync_agent(
        self, brick_name: str, tool_name: str, arguments: dict[str, Any] | None = None,
        *, task_meta: Any | None = None,
    ) -> Any:
        """Trusted in-process variant of ``call_brick_tool_sync``.

        Same behavior, routed through the 8-worker agent pool instead of the
        2-worker external-protocol pool. Use this ONLY for calls already
        running on an agent-pool worker (e.g. nested composition reached via
        ``NativeEnvelopeInvoker``/``tool_invoker_for_caller``), matching the
        Sep 14 ``native_invoker.py`` fix. A caller two agent-pool-nested
        levels deep that instead calls ``call_brick_tool_sync`` can starve
        the 2-worker proto pool permanently: every worker ends up waiting on
        a `.result()` that only another proto-pool worker (of which there
        are none free) could ever satisfy. ``call_brick_tool_sync`` itself
        is left unchanged — external MCP protocol clients still need the
        proto pool's own isolation from agent/graph nesting.
        """
        from .pools import _run_sync_agent
        return unwrap_transport(_run_sync_agent(self.call_brick_tool(
            brick_name, tool_name, arguments, task_meta=task_meta,
        )))

    def get_brick_tool_names(self, brick_name: str) -> list[str]:
        catalog = self.ensure_loaded(brick_name) if self._is_known(brick_name) else None
        if catalog is None:
            return []
        from .public_admission import project_public_tools
        projection = project_public_tools(((
            brick_name, self.get_cached_tool_map(brick_name, catalog),
        ),))
        return [item.public_name for item in projection.admitted]

    def get_all_tool_names(self) -> list[str]:
        from .public_admission import project_public_tools
        tool_maps: list[tuple[str, dict[str, Any]]] = []
        for brick in self._available:
            catalog = self.ensure_loaded(brick)
            if catalog is not None:
                tool_maps.append((brick, self.get_cached_tool_map(brick, catalog)))
        return [item.public_name for item in project_public_tools(tool_maps).admitted]
