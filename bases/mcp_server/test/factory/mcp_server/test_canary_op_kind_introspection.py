"""Frozen-contract canary for the op_kind lookup (bd:python-factory-rk4hc).

Mirrors ``test_canary_sdk_method_names_present`` — pins that the aggregator
reads the ``_mcp_op_kind`` trait off the ``FunctionTool.fn`` it holds. A
future refactor that drops the introspection (or that ToolCatalog stops exposing
``.fn``) fails loud here rather than silently emitting no ``opKind``.
"""
from __future__ import annotations

from factory.mcp_server.runtime.op_kind_lookup import (
    _SEED_OP_KIND,
    build_op_kind_lookup,
    read_op_kind,
)


class _StubTool:
    """Stand-in for a ToolCatalog FunctionTool: exposes ``.fn``."""

    def __init__(self, fn: object) -> None:
        self.fn = fn


def test_canary_mcp_op_kind_introspection() -> None:
    """``read_op_kind`` MUST read ``_mcp_op_kind`` off ``tool.fn``.

    This is the load-bearing introspection the whole Contract-A wire
    depends on. If ToolCatalog stops preserving custom attrs on ``.fn`` or a
    refactor renames the attr, this fails fast (bd:python-factory-rk4hc).
    """
    from factory.mcp_utils.interface import op_kind

    @op_kind("shell")
    def shell_tool() -> None:  # pragma: no cover - body never called
        ...

    tool = _StubTool(shell_tool)
    assert read_op_kind(tool) == "shell", (
        "Aggregator no longer reads _mcp_op_kind off FunctionTool.fn — "
        "Contract A wire (bd:python-factory-rk4hc) is broken."
    )


def test_read_op_kind_none_when_untagged() -> None:
    def plain() -> None:  # pragma: no cover - body never called
        ...

    assert read_op_kind(_StubTool(plain)) is None
    assert read_op_kind(object()) is None  # no .fn at all


def test_fastmcp_function_tool_preserves_op_kind_attr() -> None:
    """Pin the SDK assumption: ToolCatalog FunctionTool.fn keeps the trait.

    If a ToolCatalog upgrade wraps the fn and drops custom attrs, the lookup
    silently yields no opKind — this canary catches that at upgrade time.
    """
    import asyncio

    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    from factory.mcp_utils.interface import op_kind

    mcp = ToolCatalog("canary")

    @mcp.tool()
    @op_kind("shell")
    def canary_shell(x: int) -> int:  # pragma: no cover - body never called
        return x

    async def _resolve() -> object:
        return await mcp.get_tool("canary_shell")

    tool = asyncio.run(_resolve())
    assert read_op_kind(tool) == "shell"


def test_seed_covers_native_strands_tools() -> None:
    """Non-MCP strands_tools are seeded name-keyed (server-side, not IDE)."""
    assert _SEED_OP_KIND["shell"] == "shell"
    assert _SEED_OP_KIND["python_repl"] == "shell"


def test_build_lookup_includes_seed() -> None:
    """``build_op_kind_lookup`` always carries the native-tool seed even
    when no aggregator is initialised (degrades cleanly)."""
    lookup = build_op_kind_lookup()
    assert lookup["shell"] == "shell"
    assert lookup["python_repl"] == "shell"
