"""Public MCP name resolution and exact scoped composition."""
from __future__ import annotations

import pytest
from pydantic import BaseModel, ConfigDict

from factory.mcp_utils.interface import ToolResult, ok, operational, service_only
from factory.mcp_utils.runtime.tool_catalog import CatalogTool, ToolCatalog
from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.scoped_surface import (
    create_exact_flat_surface, resolve_public_names,
)


class _Input(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    value: str = ""


class _Output(_Input):
    pass


def _aggregator() -> MCPAggregator:
    catalog = ToolCatalog("demo")

    @catalog.tool(name="demo.echo")
    @operational(input_model=_Input, output_model=_Output)
    def echo(value: str = "") -> ToolResult[_Output]:
        return ok(_Output(value=value))

    @catalog.tool(name="private")
    @service_only(callers={"workflow"}, binding="attempt")
    @operational(input_model=_Input, output_model=_Output)
    def private(value: str = "") -> ToolResult[_Output]:
        return ok(_Output(value=value))

    catalog.add_tool(CatalogTool("invalid", "", lambda: {}))
    aggregator = MCPAggregator()
    aggregator.set_available_bricks(["demo"])
    aggregator._lazy._cache["demo"] = catalog
    return aggregator


def test_aliases_canonicalize_and_unknown_private_invalid_fail_closed() -> None:
    aggregator = _aggregator()
    assert resolve_public_names(aggregator, ["demo.echo"]) == {"demo_echo"}
    assert resolve_public_names(aggregator, ["demo_echo"]) == {"demo_echo"}
    for denied in ("missing", "demo_private", "demo_invalid"):
        with pytest.raises(ValueError, match="unknown or non-public"):
            resolve_public_names(aggregator, [denied])


def test_explicit_empty_is_preserved_and_child_never_exceeds_parent() -> None:
    aggregator = _aggregator()
    _server, empty = create_exact_flat_surface(aggregator, set())
    assert empty.tool_names == frozenset() and empty.delegation_depth == 0
    _server, root = create_exact_flat_surface(aggregator, {"demo.echo"})
    _server, child = create_exact_flat_surface(
        aggregator, {"demo_echo"}, parent_scope=root,
    )
    assert child.tool_names <= root.tool_names
    assert child.delegation_depth == root.delegation_depth + 1
    with pytest.raises(ValueError, match="exceeds parent"):
        create_exact_flat_surface(
            aggregator, {"demo_echo"},
            parent_scope=type(root).create("p", set()),
        )
