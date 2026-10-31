"""Partial-safe Dataset artifact resolution output."""
from __future__ import annotations

from datetime import datetime
from typing import ClassVar

from pydantic import ConfigDict, Field, computed_field, model_validator

from ...runtime.contracts import (
    DatasetExecutionPolicy,
    DatasetInputRef,
    DatasetManifest,
    DatasetProvenanceRecord,
    DatasetQualityResults,
    DatasetSnapshotRef,
    DatasetStageCheckpoint,
    DatasetToolSchemaSnapshotRef,
)


class ResolvedArtifactOutput(DatasetManifest):
    """Exact manifest fields, retaining historically partial payloads."""

    model_config = ConfigDict(extra="forbid")
    allows_null: ClassVar[bool] = True
    schema_version: str | None = None
    dataset_digest: str | None = None
    recipe_uri: str | None = None
    recipe_digest: str | None = None
    input_artifacts: list[DatasetInputRef] = Field(default_factory=list)
    context_snapshot: DatasetSnapshotRef | None = None
    tool_schema_snapshot: DatasetToolSchemaSnapshotRef | None = None
    execution_policy: DatasetExecutionPolicy | None = None
    training_views: list[str] = Field(default_factory=list)
    quality_results: DatasetQualityResults | None = None
    provenance: DatasetProvenanceRecord | None = None
    stage_adapter_versions: dict[str, str] = Field(default_factory=dict)
    stage_lineage: list[DatasetStageCheckpoint] = Field(default_factory=list)
    created_at: datetime | None = None

    @model_validator(mode="before")
    @classmethod
    def _discard_legacy_computed_fields(cls, value: object) -> object:
        if isinstance(value, dict):
            return {
                key: item for key, item in value.items()
                if key not in {
                    "context_snapshot_uri", "context_snapshot_digest",
                    "tool_schema_snapshot_uri", "tool_schema_snapshot_digest",
                }
            }
        return value

    @computed_field(return_type=str | None)
    @property
    def context_snapshot_uri(self) -> str | None:
        return self.context_snapshot.uri if self.context_snapshot else None

    @computed_field(return_type=str | None)
    @property
    def context_snapshot_digest(self) -> str | None:
        return self.context_snapshot.digest if self.context_snapshot else None

    @computed_field(return_type=str | None)
    @property
    def tool_schema_snapshot_uri(self) -> str | None:
        return self.tool_schema_snapshot.uri if self.tool_schema_snapshot else None

    @computed_field(return_type=str | None)
    @property
    def tool_schema_snapshot_digest(self) -> str | None:
        return self.tool_schema_snapshot.digest if self.tool_schema_snapshot else None

    @property
    def root(self) -> dict[str, object]:
        """Legacy in-process view for partial resolution data."""
        return self.model_dump(mode="json", exclude_none=True)


ResolvedArtifactOutput.model_rebuild()

__all__ = ["ResolvedArtifactOutput"]
