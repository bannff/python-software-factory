"""Contract tests for the shared reserved-key normalization seam (bd cig73).

``normalize_entity_properties`` is the single source of truth for relocating
caller ``properties`` keys ``type``/``labels`` to ``prop_type``/``prop_labels``.
Both the NetworkX and Neo4j adapters route writes through it, so the SAME
Entity in produces the SAME resulting properties out regardless of backend
(the agnostic tenet). These tests pin the seam directly and prove both
adapters agree without requiring a live Neo4j server.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from factory.graph.runtime.entity_contract import (
    RESERVED_NODE_ATTRS,
    normalize_entity_properties,
)
from factory.graph.runtime.ports import Entity
from factory.graph.runtime.adapters.networkx_attrs import node_attrs
from factory.graph.runtime.adapters.neo4j_adapter import Neo4jGraph


class TestNormalizeEntityProperties:
    """The shared seam in isolation."""

    def test_reserved_keys_relocated(self) -> None:
        entity = Entity(
            id="e1", type="Person", labels=["L1"],
            properties={"type": "ct", "labels": "cl"},
        )
        props = normalize_entity_properties(entity)
        assert props["prop_type"] == "ct"
        assert props["prop_labels"] == "cl"
        assert "type" not in props
        assert "labels" not in props

    def test_other_keys_untouched(self) -> None:
        entity = Entity(
            id="e1", type="Person",
            properties={"name": "Alice", "age": 30, "type": "ct"},
        )
        props = normalize_entity_properties(entity)
        assert props["name"] == "Alice"
        assert props["age"] == 30
        assert props["prop_type"] == "ct"

    def test_non_mutating(self) -> None:
        original = {"type": "ct", "keep": 1}
        entity = Entity(id="e1", type="Person", properties=original)
        normalize_entity_properties(entity)
        assert original == {"type": "ct", "keep": 1}  # caller dict intact

    def test_no_reserved_keys_is_passthrough(self) -> None:
        entity = Entity(id="e1", type="Person", properties={"a": 1, "b": 2})
        assert normalize_entity_properties(entity) == {"a": 1, "b": 2}

    def test_reserved_constant(self) -> None:
        assert RESERVED_NODE_ATTRS == ("type", "labels")


class TestCrossAdapterConsistency:
    """Same Entity -> same normalized properties on both backends."""

    def _entity(self) -> Entity:
        return Entity(
            id="e1", type="Person", labels=["Canon"],
            properties={"type": "X", "labels": "Y", "other": "Z"},
        )

    def test_networkx_matches_shared_seam(self) -> None:
        entity = self._entity()
        attrs = node_attrs(entity)
        # Canonical attrs own type/labels; caller values relocated.
        assert attrs["type"] == "Person"
        assert attrs["labels"] == ["Canon"]
        assert attrs["prop_type"] == "X"
        assert attrs["prop_labels"] == "Y"
        assert attrs["other"] == "Z"

    def test_neo4j_write_path_matches_shared_seam(self) -> None:
        """Neo4j add_entity stores prop_type/prop_labels identically.

        No live server: capture the ``props`` dict the adapter sends to
        ``session.run`` with a mocked driver and assert it equals the shared
        seam's output (plus the injected ``id``).
        """
        entity = self._entity()
        adapter = Neo4jGraph()
        session = MagicMock()
        session.__enter__.return_value = session
        session.__exit__.return_value = False
        driver = MagicMock()
        driver.session.return_value = session
        adapter._driver = driver

        adapter.add_entity(entity)

        _, kwargs = session.run.call_args
        expected = {**normalize_entity_properties(entity), "id": "e1"}
        assert kwargs["props"] == expected
        assert kwargs["props"]["prop_type"] == "X"
        assert kwargs["props"]["prop_labels"] == "Y"
        assert kwargs["props"]["other"] == "Z"
        assert "type" not in kwargs["props"]
        assert "labels" not in kwargs["props"]

    def test_both_adapters_agree_on_relocated_payload(self) -> None:
        """The relocated caller payload is identical across backends."""
        entity = self._entity()
        nx_attrs = node_attrs(entity)
        seam = normalize_entity_properties(entity)
        # Everything the seam produces appears verbatim in the NetworkX attrs.
        for key, value in seam.items():
            assert nx_attrs[key] == value
