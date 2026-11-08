"""Registry personas, graphs and swarms may only name tools the catalog serves (#404)."""
from __future__ import annotations

import pytest

from factory.agent.registry.defaults import AGENTS_TYPED, GRAPHS_TYPED, SWARMS_TYPED
from factory.agent.runtime.execution_manifest.preparation_support import partition_tools
from factory.mcp_server.core import get_config
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.brick_selection import resolve_brick_names
from factory.mcp_server.runtime.scoped_surface import resolve_public_names


@pytest.fixture(scope="module")
def aggregator() -> MCPAggregator:
    agg = MCPAggregator()
    agg.set_available_bricks(resolve_brick_names(get_config()))
    return agg


def _persona_refs() -> list[tuple[str, str]]:
    return [(f"agent:{a.id}", t) for a in AGENTS_TYPED for t in a.tools]


def _graph_refs() -> list[tuple[str, str]]:
    refs: list[tuple[str, str]] = []
    for g in GRAPHS_TYPED:
        for node in getattr(g, "nodes", []):
            refs += [(f"graph:{g.id}/{node.id}", t) for t in getattr(node, "tools", [])]
            refs += [
                (f"graph:{g.id}/{node.id}", t)
                for t in getattr(node, "mcp_tool_allowlist", None) or []
            ]
    return refs


def _swarm_refs() -> list[tuple[str, str]]:
    return [
        (f"swarm:{s.id}/{a.id}", t)
        for s in SWARMS_TYPED for a in s.agents for t in a.tools
    ]


def test_every_registry_tool_name_is_canonical_and_served(aggregator) -> None:
    refs = _persona_refs() + _graph_refs() + _swarm_refs()
    assert refs, "registries should declare at least one tool"
    bad = []
    for owner, name in refs:
        if not partition_tools([name])[1]:
            continue  # closed local built-in (think, file_read, ...), not MCP
        try:
            canonical = resolve_public_names(aggregator, [name])
        except ValueError:
            bad.append(f"{owner}: {name} (unknown)")
            continue
        if canonical != {name}:
            bad.append(f"{owner}: {name} (alias of {sorted(canonical)})")
    assert not bad, "\n".join(sorted(set(bad)))
