"""``get_tool_catalog`` — the whole-registry aggregator meta-tool (bd:3jcls.4).

The Cmd-K palette needs every operational/authoring verb across every brick
BEFORE the human has typed anything. Progressive discovery cannot supply that:
``list_bricks`` only reports already-loaded bricks and ``get_brick_tools`` is
one brick per round-trip, so a frontend-driven walk would be ~40 sequential
HTTP calls and would show a partial registry until they all landed.

So loading happens SERVER-SIDE, in-process, once. This module iterates
``LazyBrickLoader.available_bricks`` and calls the same ``ensure_loaded`` that
``EAGER_LOAD=1`` uses, then reads each tool's schema out of the loader's
existing ``_tool_cache`` (via ``get_cached_tool_map``) — there is no second
cache to drift.

Per-tool decorator traits are read by the two isolated readers in
:mod:`category_lookup` (``_mcp_category``) and :mod:`op_kind_lookup`
(``_mcp_op_kind``), so each trait has exactly one reader and its own canary.

The registry is GENERATED, never hand-maintained. The evals brick's evaluator
registry is three hand-synced literals that have already drifted
(bd:python-factory-wvkvg.22); adding a tool to any brick must make it appear
in the palette with zero frontend and zero catalog edits. Two canaries pin
that: ``test_catalog_picks_up_a_freshly_registered_tool`` and
``test_canary_mcp_category_introspection``.

Bricks that fail to load are REPORTED with their error under
``bricks_failed``, never silently omitted — a missing brick has to be visible.
"""

from __future__ import annotations

import logging
from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic
from .mcp_contracts import CatalogInput, JsonObjectOutput
from .category_lookup import read_category
from .op_kind_lookup import read_op_kind

logger = logging.getLogger(__name__)

#: Categories a human can meaningfully fire. ``deterministic`` reads are not
#: verbs; the palette asks for this subset by default.
HUMAN_CATEGORIES: tuple[str, ...] = ("operational", "authoring")

__all__ = [
    "HUMAN_CATEGORIES",
    "build_tool_catalog",
    "read_category",
    "register_catalog_tool",
    "tool_schema_entry",
]


def tool_schema_entry(
    name: str, tool: Any, input_schema: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """The ONE shape a tool schema is exposed in. One reader, one shape.

    Used by both ``LazyBrickLoader.get_brick_tools`` (progressive discovery)
    and :func:`build_tool_catalog` (the palette), so the two cannot disagree
    about a tool's category the way two hand-synced literals would.

    Both decorator traits are read here, each by its own isolated reader
    (``category_lookup.read_category`` / ``op_kind_lookup.read_op_kind``):
    ``category`` is the EFFECT axis the palette scopes on, ``op_kind`` the
    MODALITY axis (bd:python-factory-rk4hc). Either may be ``None`` — an
    undecorated tool is reported as-is rather than guessed at.
    """
    if input_schema is None:
        input_model = getattr(getattr(tool, "fn", None), "_mcp_input_model", None)
        input_schema = input_model.model_json_schema(mode="validation")
    return {
        "name": name,
        "description": getattr(tool, "description", "") or "",
        "input_schema": input_schema,
        "category": read_category(tool),
        "op_kind": read_op_kind(tool),
    }


def _qualified(brick: str, name: str) -> str:
    """Return the canonical native MCP-v2 public name."""
    from .name_resolution import canonical_tool_name
    return canonical_tool_name(brick, name)


def build_tool_catalog(
    aggregator: Any, categories: list[str] | None = None,
) -> dict[str, Any]:
    """Aggregate every brick's tool schemas into one catalog payload.

    Args:
        aggregator: The ``MCPAggregator``. Only its lazy loader is touched —
            ``available_bricks`` / ``ensure_loaded`` / ``get_cached_tool_map``,
            the same three calls ``op_kind_lookup`` makes.
        categories: ``_mcp_category`` values to keep. ``None`` = every tool
            including untagged ones. ``[]`` = nothing (strict empty).

    Returns:
        ``{"tools": [...], "count": n, "bricks_loaded": [...],
        "bricks_failed": [{"brick", "error"}], "categories": [...] | None,
        "aliases": {...}}``, where each tool is
        ``{brick, name, qualified_name, description, input_schema, category,
        op_kind}``. Never raises: a brick that blows up on import lands in
        ``bricks_failed`` with its error string.
    """
    lazy = getattr(aggregator, "_lazy", None)
    if lazy is None:
        return {
            "tools": [], "count": 0, "bricks_loaded": [],
            "bricks_failed": [], "categories": categories,
            "error": "Progressive mode not initialized",
        }

    wanted = None if categories is None else set(categories)
    tools: list[dict[str, Any]] = []
    loaded: list[str] = []
    failed: list[dict[str, str]] = []
    tool_maps: list[tuple[str, dict[str, Any]]] = []

    for brick in lazy.available_bricks:
        brick_mcp = lazy.ensure_loaded(brick)
        if brick_mcp is None:
            reg = lazy.registrations.get(brick)
            failed.append({
                "brick": brick,
                "error": (reg.error if reg and reg.error else "failed to load"),
            })
            continue
        try:
            tool_map = lazy.get_cached_tool_map(brick, brick_mcp)
        except Exception:
            logger.warning("Catalog tool map failed for brick '%s'", brick)
            failed.append({"brick": brick, "error": "tool_map_failed"})
            continue
        loaded.append(brick)
        tool_maps.append((brick, tool_map))

    from .public_admission import project_public_tools
    from .authorization import filter_projection
    projection = project_public_tools(tool_maps)
    for item in filter_projection(projection):
        entry = tool_schema_entry(
            item.source_name, item.tool, item.input_schema,
        )
        if wanted is not None and entry["category"] not in wanted:
            continue
        entry["brick"] = item.brick
        entry["qualified_name"] = item.public_name
        tools.append(entry)

    # Reuse the ONE alias table the repo already has (``ml`` →
    # ``machine_learning``). Shipping it lets the palette map an active canvas
    # view id onto a brick name without a hardcoded literal in React — the
    # kind of hand-synced list this bead exists to avoid.
    from .name_resolution import _ALIASES

    return {
        "tools": tools,
        "count": len(tools),
        "bricks_loaded": loaded,
        "bricks_failed": failed,
        "invalid_tools": list(projection.invalid_tools),
        "categories": categories,
        "aliases": dict(_ALIASES),
    }


def register_catalog_tool(mcp: Any, aggregator: Any) -> None:
    """Register the single ``get_tool_catalog`` meta-tool.

    Registration lives here rather than in ``progressive.py`` so that file
    stays under the 200-LOC ceiling.
    """
    @mcp.tool()
    @deterministic(input_model=CatalogInput, output_model=JsonObjectOutput)
    def get_tool_catalog(
        categories: list[str] | None = None,
    ) -> ToolResult[JsonObjectOutput]:
        """Get tool schemas for EVERY brick in one call (loads them all).

        The whole-registry counterpart to ``get_brick_tools``. Loading is
        server-side and in-process, so a client gets the complete registry in
        one round-trip instead of one call per brick. Bricks that fail to load
        are reported under ``bricks_failed`` with their error.

        Args:
            categories: Keep only tools whose ``_mcp_category`` is in this
                list — e.g. ``["operational", "authoring"]`` for verbs a human
                can fire. Omit for every tool.
        """
        return build_tool_catalog(aggregator, categories)
