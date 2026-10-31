"""Public scoped-native composition owned by the MCP gateway."""
from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from factory.mcp_utils.interface import CapabilityScope

from .native_v2_bootstrap import build_configured_native_server
from .public_admission import project_public_tools


def _public_projection(aggregator: Any):
    lazy = aggregator._lazy
    if lazy is None:
        return project_public_tools(())
    tool_maps = []
    for brick in lazy.available_bricks:
        catalog = lazy.ensure_loaded(brick)
        if catalog is not None:
            tool_maps.append((brick, lazy.get_cached_tool_map(brick, catalog)))
    return project_public_tools(tool_maps, normalize_dots=True)


def resolve_public_names(aggregator: Any, requested: Iterable[str]) -> frozenset[str]:
    """Canonicalize requested public names and reject every unresolved name."""
    projection = _public_projection(aggregator)
    aliases: dict[str, str] = {}
    for item in projection.admitted:
        aliases[item.public_name] = item.public_name
        aliases[item.source_name] = item.public_name
        aliases[item.source_name.replace(".", "_")] = item.public_name
    resolved: set[str] = set()
    for name in requested:
        canonical = aliases.get(name)
        if canonical is None:
            raise ValueError(f"unknown or non-public MCP capability: {name!r}")
        resolved.add(canonical)
    return frozenset(resolved)


def create_exact_flat_surface(
    aggregator: Any,
    requested: Iterable[str] | None = None,
    *,
    policy_id: str = "companion-x-agent",
    parent_scope: CapabilityScope | None = None,
) -> tuple[Any, CapabilityScope]:
    """Create an exact admitted flat server and canonical trusted scope."""
    if requested is None:
        names = (
            parent_scope.tool_names if parent_scope is not None
            else frozenset(item.public_name for item in _public_projection(
                aggregator,
            ).admitted)
        )
    else:
        names = resolve_public_names(aggregator, requested)
    if parent_scope is not None and not names <= parent_scope.tool_names:
        raise ValueError("delegated capability scope exceeds parent authority")
    depth = 0 if parent_scope is None else parent_scope.delegation_depth + 1
    policy = parent_scope.policy_id if parent_scope is not None else policy_id
    scope = CapabilityScope.create(policy, names, delegation_depth=depth)
    server, plan = build_configured_native_server(
        aggregator,
        server_name=f"companion-x-agent-{scope.digest[:12]}",
        discovery_mode="flat",
        allowlist=set(names),
    )
    if plan.selected_tools != names:
        raise RuntimeError("native MCP scoped surface does not match admitted tools")
    return server, scope


__all__ = ["create_exact_flat_surface", "resolve_public_names"]
