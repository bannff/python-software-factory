"""Ports isolating public dataset jobs from storage and worker mechanics."""
from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, TypedDict

from .contracts import (
    DatasetArtifactRef, DatasetFallbackRecord, DatasetGenerationRequest,
    DatasetJobReceipt, DatasetJobStatus, DatasetManifest,
    DatasetProvenanceRecord, DatasetQualityResults, DatasetStageCheckpoint,
)
from .definition_models import (
    DefinitionArtifact, DefinitionArtifactPublishResult, DefinitionArtifactRef,
)
from .scenario_models import (
    ScenarioPack, ScenarioPackDraft, ScenarioPackGenerationInput,
    ScenarioPackLineage, ScenarioPackPublishResult, ScenarioPackRef,
)
from .blueprint_models import (
    BlueprintResolution, DatasetBlueprint, DatasetBlueprintBinding,
    DatasetHumanApprovalRef, DatasetQualityPolicyRef,
)
from .blueprint_results import DatasetBlueprintPublishResult
from .dbc_models import DbcCatalogEntry
from .failure_pattern_models import FailurePatternRef, FailurePatternSpec


class DbcCatalogPort(Protocol):
    """Transport-neutral approved DBC catalog boundary."""

    def list_entries(self) -> tuple[DbcCatalogEntry, ...]: ...
    def get_entry(self, catalog_id: str, version: str = "") -> DbcCatalogEntry | None: ...
    def verified_path(self, entry: DbcCatalogEntry) -> Path: ...


class FailurePatternStorePort(Protocol):
    """Immutable lookup boundary for versioned failure patterns."""

    def list_refs(self) -> tuple[FailurePatternRef, ...]: ...
    def load(self, ref: FailurePatternRef) -> FailurePatternSpec: ...
    def inspect(self, pattern_id: str, version: str = "") -> FailurePatternSpec: ...


class GraphEntityResult(TypedDict):
    """Validated ``data`` payload from a successful typed Graph entity result."""

    id: str
    type: str
    properties: dict[str, Any]
    labels: list[str]


class GraphRelationshipResult(TypedDict):
    """Validated ``data`` payload from a successful typed Graph relationship result."""

    id: str
    type: str
    source_id: str
    target_id: str
    properties: dict[str, Any]


class GraphProjectionPort(Protocol):
    """Fail-closed named-MCP projection boundary owned by Dataset."""

    def add_entity(
        self, entity_id: str, entity_type: str, properties: dict[str, Any],
    ) -> GraphEntityResult: ...
    def add_relationship(
        self, relationship_id: str, relationship_type: str,
        source_id: str, target_id: str, properties: dict[str, Any],
    ) -> GraphRelationshipResult: ...


class DatasetJobStorage(Protocol):
    def create_job(self, request: DatasetGenerationRequest) -> DatasetJobReceipt: ...
    def get_job(self, job_id: str) -> DatasetJobStatus | None: ...
    def save_job(self, status: DatasetJobStatus) -> None: ...
    def get_artifact(self, job_id: str) -> DatasetArtifactRef | None: ...
    def resolve_manifest(self, dataset_uri: str) -> DatasetManifest | None: ...


class DatasetJobExecutor(Protocol):
    def submit(self, job_id: str) -> None: ...


class DatasetTerminalStore(Protocol):
    """Durable create-or-match boundary for synchronous terminal attempts."""

    def lock(self, attempt_id: str) -> AbstractContextManager[None]: ...
    def claim(self, attempt_id: str, request_sha256: str) -> tuple[str, Any]: ...
    def transition(self, record: Any, state: str) -> Any: ...
    def publish(self, record: Any, terminal: dict[str, Any]) -> Any: ...
    def load_terminal(self, record: Any) -> dict[str, Any]: ...


class DatasetMaterializer(Protocol):
    def materialize(self, status: DatasetJobStatus) -> DatasetArtifactRef: ...

    @property
    def root(self) -> Path: ...


class DatasetStagePort(Protocol):
    name: str
    stage_version: str

    def execute(
        self, records: Iterable[Any], config: Mapping[str, Any] | None = None,
    ) -> Iterator[Any]: ...


class DatasetStageCheckpointStore(Protocol):
    def save(
        self, *, stage_name: str, stage_index: int, input_digest: str,
        records: list[Any], schema_version: str, adapter_version: str,
        config: Mapping[str, Any] | None = None, context_snapshot_digest: str,
        tool_schema_snapshot_digest: str, provenance: DatasetProvenanceRecord,
        quality_results: DatasetQualityResults,
        fallback: DatasetFallbackRecord | None = None,
        scenario_lineage: ScenarioPackLineage | None = None,
    ) -> DatasetStageCheckpoint: ...


class DefinitionArtifactStorePort(Protocol):
    """Immutable, bounded definition publication and resolution boundary."""

    def publish(
        self, artifact: DefinitionArtifact,
    ) -> DefinitionArtifactPublishResult: ...
    def resolve(self, ref: DefinitionArtifactRef) -> DefinitionArtifact: ...


class ScenarioPackStorePort(Protocol):
    def publish(self, draft: ScenarioPackDraft) -> ScenarioPackPublishResult: ...
    def load(self, ref: ScenarioPackRef) -> ScenarioPack: ...


class EpisodeGeneratorPort(Protocol):
    def generate(
        self, pack: ScenarioPack, request: ScenarioPackGenerationInput,
    ) -> tuple[list[dict[str, Any]], ScenarioPackLineage]: ...


class DatasetBlueprintStorePort(Protocol):
    def publish(self, blueprint: DatasetBlueprint) -> DatasetBlueprintPublishResult: ...
    def load(self, binding: DatasetBlueprintBinding) -> DatasetBlueprint: ...


class DatasetHumanApprovalPort(Protocol):
    def require(
        self, ref: DatasetHumanApprovalRef, blueprint_digest: str,
        quality_policy: DatasetQualityPolicyRef,
    ) -> None: ...


class DatasetQualityPolicyPort(Protocol):
    def require(self, ref: DatasetQualityPolicyRef) -> None: ...


class DatasetReferenceRegistryPort(Protocol):
    def validate(self, blueprint: DatasetBlueprint) -> BlueprintResolution: ...


class CompletionPort(Protocol):
    """Bound single-shot completion boundary consumed by generation stages."""
    def get_completion(
        self, prompt: str, *, system_prompt: str | None = None,
        temperature: float | None = None, max_tokens: int | None = None,
    ) -> str: ...
