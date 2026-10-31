"""Per-domain graph taxonomy registry tests.

bd:python-factory-qm07q (epic python-factory-hadbi). ``security`` ->
SECURITY_TAXONOMY view; unknown -> None; registration is append-only;
``get_extensions`` snapshots are frozen; ``merge_taxonomies`` is
last-write-wins; fuzz over alphanumeric+dash domain ids round-trips.
Test isolation: autouse fixture calls ``reset_extensions``.
"""
from __future__ import annotations

import pytest
from hypothesis import HealthCheck, assume, given, settings, strategies as st

from factory.graph.mcp.docs_security_taxonomy import SECURITY_TAXONOMY
from factory.graph.runtime.taxonomy_registry import (
    get_extensions,
    merge_taxonomies,
    register_extension,
    reset_extensions,
    resolve_domain_taxonomy,
)


SETTINGS = settings(
    max_examples=40, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)

WINE_NODE_TYPES = {"Vintage": {"description": "A wine vintage observation.",
                               "required_properties": ["year", "varietal"]}}
WINE_REL_TYPES = {"PAIRED_WITH": {"description": "Vintage paired with a dish.",
                                  "source": "Vintage", "target": "Dish"}}
WINE_CONVENTIONS = {"id_format": "vintage-<year>-<varietal>"}


@pytest.fixture(autouse=True)
def _isolation() -> None:
    reset_extensions()
    yield
    reset_extensions()


def test_security_default_returns_security_taxonomy() -> None:
    result = resolve_domain_taxonomy("security")
    # Byte-identical to SECURITY_TAXONOMY (no leakage, no key drift).
    assert result == SECURITY_TAXONOMY
    assert "Finding" in result["node_labels"]
    assert "DISCOVERED" in result["relationship_types"]


def test_security_default_returns_deepcopy() -> None:
    a = resolve_domain_taxonomy("security")
    a["node_labels"]["MutatedKey"] = {"oh": "no"}
    b = resolve_domain_taxonomy("security")
    assert "MutatedKey" not in b["node_labels"]


def test_unknown_domain_returns_none() -> None:
    assert resolve_domain_taxonomy("wine_pairing") is None
    assert resolve_domain_taxonomy("") is None
    assert resolve_domain_taxonomy("nope") is None


def test_register_extension_appends_node_types() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES, conventions=WINE_CONVENTIONS,
    )
    extensions = get_extensions()
    assert "wine_pairing" in extensions
    assert "Vintage" in extensions["wine_pairing"]["node_types"]
    assert "PAIRED_WITH" in extensions["wine_pairing"]["relationship_types"]


def test_register_extension_collision_raises_value_error() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES,
    )
    with pytest.raises(ValueError, match="already registered"):
        register_extension(
            "wine_pairing", node_types={"OtherNode": {}},
            relationship_types={},
        )


def test_resolve_merges_base_plus_extension() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES, conventions=WINE_CONVENTIONS,
    )
    result = resolve_domain_taxonomy("wine_pairing")
    assert result is not None
    assert "Finding" in result["node_types"]  # security base preserved
    assert "Vintage" in result["node_types"]  # extension added
    assert "PAIRED_WITH" in result["relationship_types"]
    assert result["conventions"]["id_format"] == "vintage-<year>-<varietal>"


def test_resolve_extension_does_not_mutate_security_default() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES,
    )
    _ = resolve_domain_taxonomy("wine_pairing")
    sec = resolve_domain_taxonomy("security")
    assert "Vintage" not in sec["node_labels"]


def test_get_extensions_returns_frozen_snapshot() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES,
    )
    snapshot = get_extensions()
    snapshot["wine_pairing"]["node_types"]["Hacked"] = {"oh": "no"}
    snapshot["malicious"] = {"node_types": {}, "relationship_types": {}}
    fresh = get_extensions()
    assert "Hacked" not in fresh["wine_pairing"]["node_types"]
    assert "malicious" not in fresh


def test_reset_extensions_clears_all() -> None:
    register_extension(
        "wine_pairing", node_types=WINE_NODE_TYPES,
        relationship_types=WINE_REL_TYPES,
    )
    register_extension(
        "workouts", node_types={"Exercise": {}}, relationship_types={},
    )
    assert len(get_extensions()) == 2
    reset_extensions()
    assert get_extensions() == {}


def test_merge_taxonomies_empty() -> None:
    merged = merge_taxonomies()
    assert merged == {"node_types": {}, "relationship_types": {}, "conventions": {}}


def test_merge_taxonomies_last_write_wins_on_key_collision() -> None:
    base = {"node_types": {"A": {"src": "base"}}}
    ext = {"node_types": {"A": {"src": "ext"}}}
    merged = merge_taxonomies(base, ext)
    assert merged["node_types"]["A"]["src"] == "ext"


def test_merge_taxonomies_preserves_top_level_metadata() -> None:
    base = {"version": "1.0", "node_types": {"X": {}}, "relationship_types": {}}
    ext = {"node_types": {"Y": {}}, "relationship_types": {}}
    merged = merge_taxonomies(base, ext)
    assert merged["version"] == "1.0"


_DOMAIN_ID_ALPHABET = st.text(
    alphabet=st.sampled_from(
        "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-"
    ),
    min_size=1, max_size=24,
)


@given(domain_id=_DOMAIN_ID_ALPHABET)
@SETTINGS
def test_register_resolve_roundtrip(domain_id: str) -> None:
    assume(domain_id != "security")
    reset_extensions()
    register_extension(
        domain_id,
        node_types={"Custom": {"description": "x"}},
        relationship_types={"CUSTOM_REL": {"source": "A", "target": "B"}},
    )
    result = resolve_domain_taxonomy(domain_id)
    assert result is not None
    assert "Custom" in result["node_types"]
    assert "CUSTOM_REL" in result["relationship_types"]


@given(
    a_node=st.text(min_size=1, max_size=10,
                   alphabet=st.characters(whitelist_categories=("L",))),
    b_node=st.text(min_size=1, max_size=10,
                   alphabet=st.characters(whitelist_categories=("L",))),
)
@SETTINGS
def test_merge_taxonomies_associativity(a_node: str, b_node: str) -> None:
    """``merge(merge(a,b),c) == merge(a,merge(b,c))`` when keys are disjoint."""
    assume(a_node != b_node)
    a = {"node_types": {a_node: {"x": 1}}, "relationship_types": {}}
    b = {"node_types": {b_node: {"y": 2}}, "relationship_types": {}}
    c = {"node_types": {"Z": {"z": 3}}, "relationship_types": {}}
    left = merge_taxonomies(merge_taxonomies(a, b), c)
    right = merge_taxonomies(a, merge_taxonomies(b, c))
    assert left["node_types"] == right["node_types"]
