"""Tests for ``get_tool_catalog`` — the Cmd-K registry (bd:3jcls.4).

NOT MOCKED. These run against the real ``LazyBrickLoader`` importing real
bricks, because the whole point of the catalog is that it reflects what the
process actually loaded. A mocked loader would happily prove a catalog that
does not exist — the failure mode an earlier audit found shipping.
"""

from __future__ import annotations

import pytest

from factory.mcp_server.runtime.lazy_loader import LazyBrickLoader
from factory.mcp_server.runtime.tool_catalog import (
    HUMAN_CATEGORIES,
    build_tool_catalog,
    read_category,
    tool_schema_entry,
)

from .typed_tool_fixtures import EmptyInput, add_value_tool

#: Real, cheap-to-import bricks. ``cache`` and ``ui`` both ship @operational
#: tools; ``ui`` owns ``ui_dispatch_action`` itself.
_REAL_BRICKS = ["cache", "ui"]


class _Agg:
    """Minimal stand-in for MCPAggregator: the catalog only reads ``_lazy``.

    The LOADER is real; this is just the attribute the builder reaches through
    (same seam ``op_kind_lookup`` uses).
    """

    def __init__(self, lazy: LazyBrickLoader) -> None:
        self._lazy = lazy


@pytest.fixture(scope="module")
def real_loader() -> LazyBrickLoader:
    loader = LazyBrickLoader()
    loader.set_available(list(_REAL_BRICKS))
    return loader


@pytest.fixture(scope="module")
def agg(real_loader: LazyBrickLoader) -> _Agg:
    return _Agg(real_loader)


def test_catalog_loads_real_bricks(agg: _Agg) -> None:
    """A brick that was never touched still appears — loading is server-side."""
    catalog = build_tool_catalog(agg, None)
    assert catalog["count"] > 0
    assert set(catalog["bricks_loaded"]) == set(_REAL_BRICKS), catalog["bricks_failed"]


def test_catalog_entries_carry_brick_and_qualified_name(agg: _Agg) -> None:
    catalog = build_tool_catalog(agg, None)
    entry = next(t for t in catalog["tools"] if t["name"].endswith("dispatch_action"))
    assert entry["brick"] == "ui"
    assert entry["qualified_name"] == "ui_dispatch_action"
    assert entry["category"] == "operational"
    assert isinstance(entry["input_schema"], dict)
    # Both decorator axes ride along; op_kind is None for tools that don't
    # declare a modality (bd:python-factory-rk4hc).
    assert "op_kind" in entry


def test_category_filter_excludes_deterministic(agg: _Agg) -> None:
    """The palette asks for verbs only; reads are not verbs a human fires."""
    human = build_tool_catalog(agg, list(HUMAN_CATEGORIES))
    assert human["count"] > 0
    assert {t["category"] for t in human["tools"]} <= set(HUMAN_CATEGORIES)
    everything = build_tool_catalog(agg, None)
    assert everything["count"] > human["count"], (
        "expected at least one @deterministic tool to be filtered out"
    )


def test_empty_category_list_is_strict_empty(agg: _Agg) -> None:
    """``[]`` matches nothing; ``None`` matches everything. Not interchangeable."""
    assert build_tool_catalog(agg, [])["count"] == 0
    assert build_tool_catalog(agg, None)["count"] > 0


def test_failed_brick_is_reported_not_omitted() -> None:
    """A brick that cannot load must be VISIBLE with its error."""
    loader = LazyBrickLoader()
    loader.set_available(["cache", "no_such_brick_xyz"])
    catalog = build_tool_catalog(_Agg(loader), None)
    failed = {f["brick"]: f["error"] for f in catalog["bricks_failed"]}
    assert "no_such_brick_xyz" in failed
    assert failed["no_such_brick_xyz"]
    assert "cache" in catalog["bricks_loaded"]


def test_uninitialised_progressive_mode_degrades_cleanly() -> None:
    class _NoLazy:
        _lazy = None

    catalog = build_tool_catalog(_NoLazy(), None)
    assert catalog["count"] == 0
    assert catalog["error"]


def test_catalog_picks_up_a_freshly_registered_tool(
    real_loader: LazyBrickLoader,
) -> None:
    """ANTI-DRIFT CANARY 1 — the registry is GENERATED, never hand-listed.

    Register a throwaway ``@operational`` tool on a REAL loaded brick and
    assert it shows up in the catalog with zero catalog edits and zero
    frontend edits. If someone ever replaces the aggregation with a
    hand-maintained literal (the evals evaluator-registry mistake,
    bd:python-factory-wvkvg.22 — three hand-synced files that already drifted),
    this fails.
    """
    brick_mcp = real_loader.ensure_loaded("cache")
    assert brick_mcp is not None

    add_value_tool(brick_mcp, "canary_throwaway_verb")

    # The loader caches name→tool maps; a new registration invalidates it.
    real_loader._tool_cache.pop("cache", None)
    try:
        catalog = build_tool_catalog(_Agg(real_loader), list(HUMAN_CATEGORIES))
        names = {t["qualified_name"] for t in catalog["tools"]}
        assert "cache_canary_throwaway_verb" in names, (
            "A newly registered @operational tool did not reach the catalog — "
            "the palette registry is no longer generated from the live "
            "aggregator (bd:3jcls.4 anti-drift condition 1)."
        )
        entry = next(
            t for t in catalog["tools"]
            if t["qualified_name"] == "cache_canary_throwaway_verb"
        )
        assert entry["category"] == "operational"
        assert "value" in entry["input_schema"].get("properties", {})
    finally:
        real_loader._tool_cache.pop("cache", None)
        real_loader.invalidate("cache")


def test_progressive_discovery_and_catalog_share_one_shape(
    real_loader: LazyBrickLoader,
) -> None:
    """``get_brick_tools`` and the catalog must not disagree about category.

    Both go through :func:`tool_schema_entry`, so a tool's category is read
    once from one place. Pin that structurally.
    """
    per_brick = real_loader.get_brick_tools("ui")
    by_name = {t["name"]: t for t in per_brick["tools"]}
    assert all("category" in t and "op_kind" in t for t in per_brick["tools"])

    catalog = build_tool_catalog(_Agg(real_loader), None)
    for entry in (t for t in catalog["tools"] if t["brick"] == "ui"):
        assert entry["category"] == by_name[entry["name"]]["category"]
        assert entry["op_kind"] == by_name[entry["name"]]["op_kind"]
        assert entry["description"] == by_name[entry["name"]]["description"]


def test_tool_schema_entry_shape_is_fixed() -> None:
    """The frontend consumes these keys by name — pin the whole set."""
    class _T:
        description = "d"
        fn = type("Handler", (), {"_mcp_input_model": EmptyInput})()

    entry = tool_schema_entry("t", _T())
    assert set(entry.keys()) == {
        "name", "description", "input_schema", "category", "op_kind",
    }
    assert entry["category"] is None and entry["op_kind"] is None
    assert read_category(_T()) is None
