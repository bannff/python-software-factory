"""``tool_name -> op_kind`` lookup built by introspecting decorated fns.

Contract A (bd:python-factory-rk4hc, Req 15.3). The aggregator holds the
decorated brick-tool fns IN-PROCESS — each carries an optional
``_mcp_op_kind`` trait set by ``factory.mcp_utils.interface.op_kind``. This
module builds a name-keyed lookup the chat adapter reads to stamp ``opKind``
onto the terminal-mirror wire. No MCP-boundary crossing: the aggregator only
READS the trait off the ``FunctionTool.fn`` it already holds (tenet #6 — the
base stays a transport shell; this is registration plumbing).

Non-MCP ``strands_tools`` (``shell`` / ``python_repl``) carry no FastMCP
``_meta`` and have no decorated fn to introspect — they are seeded
name-keyed here (a server-side map, NOT IDE hardcoding).
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Native strands_tools have no decorated fn — seed their modality by name.
_SEED_OP_KIND: dict[str, str] = {"shell": "shell", "python_repl": "shell"}


def read_op_kind(tool: Any) -> str | None:
    """Introspect a FastMCP ``FunctionTool``'s underlying fn for ``_mcp_op_kind``.

    Isolated so the regression guard (``test_canary_mcp_op_kind_introspection``)
    can pin that the aggregator reads the ``_mcp_op_kind`` attribute — a
    future refactor that drops the introspection fails loud.
    """
    fn = getattr(tool, "fn", None)
    return getattr(fn, "_mcp_op_kind", None) if fn is not None else None


def build_op_kind_lookup() -> dict[str, str]:
    """Build a ``tool_name -> op_kind`` map across all loaded bricks + seed.

    Keys both the brick-native name and its dot→underscore-normalised form
    (the flat-view rewrites ``foo.bar`` to ``foo_bar`` for Bedrock, so the
    chat agent sees the underscore form). Seeds non-MCP ``strands_tools`` by
    name. Bricks that fail to load are skipped (logged, never raised).
    """
    from .. import interface as _iface

    lookup: dict[str, str] = dict(_SEED_OP_KIND)
    agg = _iface.get_aggregator()
    if agg is None or getattr(agg, "_lazy", None) is None:
        return lookup
    for brick in agg._lazy.available_bricks:
        brick_mcp = agg._lazy.ensure_loaded(brick)
        if brick_mcp is None:
            continue
        tool_map = agg._lazy.get_cached_tool_map(brick, brick_mcp)
        for name, tool in tool_map.items():
            kind = read_op_kind(tool)
            if kind is None:
                continue
            lookup[name] = kind
            lookup[name.replace(".", "_")] = kind
    return lookup
