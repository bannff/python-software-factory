"""``tool_name -> category`` lookup built by introspecting decorated fns.

Sibling of :mod:`op_kind_lookup`, deliberately an exact structural mirror of
it. Where that module reads the operational-MODALITY axis (``_mcp_op_kind``),
this one reads the EFFECT axis (``_mcp_category``) set by
``factory.mcp_utils.interface.{deterministic,operational,authoring}``.

Before bd:3jcls.4 there was NO production reader for ``_mcp_category`` at all
— the decorators set the attribute and nothing ever looked at it, so nothing
guarded it. The Cmd-K palette's entire scoping rule ("@operational and
@authoring are verbs a human can fire; @deterministic reads are not") now
depends on that trait being readable off the decorated fn, which is why the
reader is isolated here with its own canary
(``test_canary_mcp_category_introspection``).

Same in-process approach as its sibling: the aggregator already holds the
decorated fns, so this only READS the trait off the ``FunctionTool.fn`` it
already has — no MCP-boundary crossing (tenet #6 — the base stays a transport
shell; this is registration plumbing). Bricks that fail to load are skipped
and logged, never raised.

Unlike ``op_kind`` there is no name-keyed seed: native ``strands_tools``
(``shell`` / ``python_repl``) are not factory MCP tools, carry no category,
and are not palette verbs.
"""
from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

#: The closed set of ``_mcp_category`` values the decorators can set.
CATEGORIES: frozenset[str] = frozenset({"deterministic", "operational", "authoring"})


def read_category(tool: Any) -> str | None:
    """Introspect a FastMCP ``FunctionTool``'s underlying fn for ``_mcp_category``.

    Isolated so the regression guard (``test_canary_mcp_category_introspection``)
    can pin that the catalog reads the ``_mcp_category`` attribute — a future
    refactor that drops the introspection, or a FastMCP upgrade that wraps the
    fn and drops custom attrs, fails loud instead of silently reporting every
    tool as uncategorised (which would render an EMPTY palette).
    """
    fn = getattr(tool, "fn", None)
    return getattr(fn, "_mcp_category", None) if fn is not None else None


def build_category_lookup() -> dict[str, str]:
    """Build a ``tool_name -> category`` map across all loaded bricks.

    Keys both the brick-native name and its dot→underscore-normalised form
    (the flat-view rewrites ``foo.bar`` to ``foo_bar`` for Bedrock, so an
    agent-facing consumer sees the underscore form) — same keying as
    ``build_op_kind_lookup``. Bricks that fail to load are skipped (logged,
    never raised).

    This is the flat, name-keyed form for consumers that only need "what kind
    of effect does this tool have?". :func:`tool_catalog.build_tool_catalog` is
    the richer consumer of the same introspection — it keeps per-brick
    grouping, input schemas, and load failures, which the palette needs.
    """
    from .. import interface as _iface

    lookup: dict[str, str] = {}
    agg = _iface.get_aggregator()
    if agg is None or getattr(agg, "_lazy", None) is None:
        return lookup
    for brick in agg._lazy.available_bricks:
        brick_mcp = agg._lazy.ensure_loaded(brick)
        if brick_mcp is None:
            logger.debug("Category lookup: skipping unloadable brick '%s'", brick)
            continue
        tool_map = agg._lazy.get_cached_tool_map(brick, brick_mcp)
        for name, tool in tool_map.items():
            category = read_category(tool)
            if category is None:
                continue
            lookup[name] = category
            lookup[name.replace(".", "_")] = category
    return lookup
