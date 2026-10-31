"""Frozen-contract canary for the ``_mcp_category`` reader (bd:3jcls.4).

Deliberately mirrors ``test_canary_op_kind_introspection.py``. Before the
Cmd-K palette, NOTHING in the repo read ``_mcp_category`` — the decorators in
``mcp_utils/decorators.py`` set the trait and no consumer ever looked at it.
The palette's whole scoping rule ("@operational and @authoring only; reads are
not verbs a human fires") now depends on that trait being readable off the
decorated fn, so it needs the same loud guard the op_kind wire got.

If a ToolCatalog upgrade wraps the fn and drops custom attrs, or a refactor
renames the trait, the palette would silently show ZERO tools (every category
reads as ``None``, every entry filtered out). These tests fail first.
"""

from __future__ import annotations

from factory.mcp_server.runtime.category_lookup import (
    CATEGORIES,
    build_category_lookup,
    read_category,
)
from factory.mcp_server.runtime.tool_catalog import (
    HUMAN_CATEGORIES,
    tool_schema_entry,
)

from .typed_tool_fixtures import add_value_tool


class _StubTool:
    """Stand-in for a ToolCatalog FunctionTool: exposes ``.fn``."""

    def __init__(self, fn: object) -> None:
        self.fn = fn


def test_canary_mcp_category_introspection() -> None:
    """``read_category`` MUST read ``_mcp_category`` off ``tool.fn``.

    The load-bearing introspection behind the palette's category scoping
    (bd:3jcls.4). Mirrors ``test_canary_mcp_op_kind_introspection``.
    """
    from factory.mcp_utils.interface import authoring, deterministic, operational

    @operational
    def op_tool() -> None:  # pragma: no cover - body never called
        ...

    @authoring
    def authoring_tool() -> None:  # pragma: no cover - body never called
        ...

    @deterministic
    def read_tool() -> None:  # pragma: no cover - body never called
        ...

    assert read_category(_StubTool(op_tool)) == "operational", (
        "Catalog no longer reads _mcp_category off FunctionTool.fn — the "
        "Cmd-K palette (bd:3jcls.4) would show zero tools."
    )
    assert read_category(_StubTool(authoring_tool)) == "authoring"
    assert read_category(_StubTool(read_tool)) == "deterministic"


def test_read_category_none_when_untagged() -> None:
    def plain() -> None:  # pragma: no cover - body never called
        ...

    assert read_category(_StubTool(plain)) is None
    assert read_category(object()) is None  # no .fn at all


def test_fastmcp_function_tool_preserves_category_attr() -> None:
    """Pin the SDK assumption: ToolCatalog ``FunctionTool.fn`` keeps the trait.

    Same posture as ``test_fastmcp_function_tool_preserves_op_kind_attr`` — a
    ToolCatalog upgrade that wraps the fn breaks the palette silently, so catch it
    at upgrade time.
    """
    import asyncio

    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    mcp = ToolCatalog("category-canary")
    add_value_tool(mcp, "canary_verb")

    async def _resolve() -> object:
        return await mcp.get_tool("canary_verb")

    tool = asyncio.run(_resolve())
    assert read_category(tool) == "operational"
    assert tool_schema_entry("canary_verb", tool)["category"] == "operational"


def test_human_categories_exclude_deterministic() -> None:
    """The scoping rule itself, pinned: reads are not verbs."""
    assert set(HUMAN_CATEGORIES) == {"operational", "authoring"}
    assert "deterministic" not in HUMAN_CATEGORIES
    assert set(HUMAN_CATEGORIES) < CATEGORIES


def test_every_decorator_value_is_readable() -> None:
    """Each of the three decorators must round-trip through the reader.

    Pins the closed value set against the decorators themselves, so adding a
    fourth category without teaching the reader about it is caught here rather
    than by tools quietly vanishing from the palette.
    """
    from factory.mcp_utils.interface import authoring, deterministic, operational

    read = {}
    for decorator in (deterministic, operational, authoring):

        def fn() -> None:  # pragma: no cover - body never called
            ...

        read[read_category(_StubTool(decorator(fn)))] = True
    assert set(read) == CATEGORIES


def test_build_category_lookup_degrades_cleanly() -> None:
    """No initialised aggregator → empty map, never an exception.

    Mirrors ``test_build_lookup_includes_seed``: the loop skips bricks that
    cannot load and logs instead of raising, so a broken brick can never take
    the lookup (or the palette) down with it.
    """
    assert isinstance(build_category_lookup(), dict)
