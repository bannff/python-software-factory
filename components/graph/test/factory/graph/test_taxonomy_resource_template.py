"""MCP-resource-level tests for ``graph://schemas/taxonomy/{domain}``.

bd:python-factory-qm07q (epic python-factory-hadbi). Pins the wire-shape
of the parametric resource template added in ``mcp/resources.py``:

* ``graph://schemas/taxonomy/security`` -> SECURITY_TAXONOMY shape.
* ``graph://schemas/taxonomy/<unknown>`` -> 404-shape JSON
  (``error`` + ``available_domains`` keys).
* ``graph://schemas/taxonomy/<registered>`` -> security base merged with
  the extension's node_types / relationship_types.
"""
from __future__ import annotations

import asyncio
import json

import pytest

from factory.graph.runtime.runtime import reset_runtime
from factory.graph.runtime.taxonomy_registry import (
    register_extension,
    reset_extensions,
)
from factory.graph.server import create_mcp_server


@pytest.fixture(autouse=True)
def _isolation():
    reset_runtime()
    reset_extensions()
    yield
    reset_runtime()
    reset_extensions()


async def _read_resource(server, uri: str) -> str:
    result = await server.read_resource(uri)
    # Native catalog returns a ResourceResult; first entry's content.
    return result.contents[0].content


def _read(server, uri: str) -> str:
    return asyncio.run(_read_resource(server, uri))


def test_security_resource_returns_security_taxonomy_shape() -> None:
    server = create_mcp_server()
    body = _read(server, "graph://schemas/taxonomy/security")
    payload = json.loads(body)
    assert "version" in payload
    assert "Finding" in payload["node_labels"]
    assert "DISCOVERED" in payload["relationship_types"]


def test_unknown_domain_returns_404_shape() -> None:
    server = create_mcp_server()
    body = _read(server, "graph://schemas/taxonomy/wine_pairing")
    payload = json.loads(body)
    assert payload["error"].startswith("Domain 'wine_pairing'")
    assert "security" in payload["available_domains"]


def test_unknown_domain_lists_registered_extensions() -> None:
    server = create_mcp_server()
    register_extension(
        "workouts",
        node_types={"Exercise": {"description": "x"}},
        relationship_types={"REPS_OF": {"source": "A", "target": "B"}},
    )
    body = _read(server, "graph://schemas/taxonomy/totally_unknown")
    payload = json.loads(body)
    assert "workouts" in payload["available_domains"]


def test_registered_domain_returns_merged_shape() -> None:
    server = create_mcp_server()
    register_extension(
        "wine_pairing",
        node_types={
            "Vintage": {
                "description": "A wine vintage observation.",
                "required_properties": ["year", "varietal"],
            },
        },
        relationship_types={
            "PAIRED_WITH": {
                "description": "Vintage paired with a dish.",
                "source": "Vintage", "target": "Dish",
            },
        },
        conventions={"id_format": "vintage-<year>-<varietal>"},
    )
    body = _read(server, "graph://schemas/taxonomy/wine_pairing")
    payload = json.loads(body)
    # Security base node_types preserved
    assert "Finding" in payload["node_types"]
    # Wine extension node_types added
    assert "Vintage" in payload["node_types"]
    # Wine relationship type added
    assert "PAIRED_WITH" in payload["relationship_types"]
    # Conventions merged
    assert payload["conventions"]["id_format"] == "vintage-<year>-<varietal>"


def test_existing_taxonomy_resource_unchanged() -> None:
    """Back-compat: ``graph://schemas/taxonomy`` still returns full union."""
    server = create_mcp_server()
    body = _read(server, "graph://schemas/taxonomy")
    payload = json.loads(body)
    assert "node_types" in payload
    assert "Finding" in payload["node_types"]


def test_existing_security_taxonomy_resource_unchanged() -> None:
    """Back-compat: ``graph://schemas/security-taxonomy`` still works."""
    server = create_mcp_server()
    body = _read(server, "graph://schemas/security-taxonomy")
    payload = json.loads(body)
    assert "node_labels" in payload
    assert "Finding" in payload["node_labels"]
