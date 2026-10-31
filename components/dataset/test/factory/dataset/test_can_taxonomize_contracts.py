"""Builder and recipe contracts for the CAN taxonomy projection stage."""
from __future__ import annotations

import hashlib

from factory.dataset.runtime.adapters._can_taxonomize_builder import TaxonomyBuilder
from factory.dataset.runtime.contracts import (
    DatasetExecutionPolicy, DatasetGenerationRequest, DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from factory.dataset.runtime.local import LocalDatasetMaterializer, LocalDatasetStore
from factory.dataset.runtime.recipe import resolve_recipe

from .test_can_taxonomize import _record


class RecordingProjection:
    def __init__(self) -> None:
        self.entities: list[tuple[str, str, dict]] = []
        self.relationships: list[tuple[str, str, str, str, dict]] = []

    def add_entity(self, entity_id, entity_type, properties):
        self.entities.append((entity_id, entity_type, properties))

    def add_relationship(self, relationship_id, relationship_type,
                         source_id, target_id, properties):
        self.relationships.append((relationship_id, relationship_type,
                                   source_id, target_id, properties))


def test_builder_commits_only_through_projection_port() -> None:
    builder = TaxonomyBuilder()
    builder.absorb(_record())
    projection = RecordingProjection()
    assert builder.commit(projection) == len(projection.entities)
    assert projection.entities and projection.relationships


def test_builder_handles_minimal_record() -> None:
    builder = TaxonomyBuilder()
    tags = builder.absorb({"timestamp_ns": 100, "arbitration_id": "0x1"})
    projection = RecordingProjection()
    builder.commit(projection)
    assert len(tags) == 1
    assert any(entity_type == "Frame" for _, entity_type, _ in projection.entities)
    assert "vehicle-None" not in tags


def _request(uri: str) -> DatasetGenerationRequest:
    return DatasetGenerationRequest(
        recipe_uri=uri, recipe_digest=hashlib.sha256(uri.encode()).hexdigest(),
        context_snapshot=DatasetSnapshotRef(
            uri="file:///tmp/x.json", digest=hashlib.sha256(b"x").hexdigest(),
        ),
        tool_schema_snapshot=DatasetToolSchemaSnapshotRef(
            uri="file:///tmp/x.json", digest=hashlib.sha256(b"x").hexdigest(),
            allowed_tools=[],
        ),
        execution_policy=DatasetExecutionPolicy(),
    )


def test_can_taxonomize_recipe_uri_resolves() -> None:
    recipe = resolve_recipe(_request("recipe://local/can-taxonomize@1"))
    assert [stage.name for stage in recipe.stages] == ["can_taxonomize"]
    assert recipe.record_schema == "can_frame"


def test_can_taxonomize_registered_in_default_stages(tmp_path) -> None:
    store = LocalDatasetStore(tmp_path / "store")
    materializer = LocalDatasetMaterializer(store)
    assert materializer.stages["can_taxonomize"].name == "can_taxonomize"
