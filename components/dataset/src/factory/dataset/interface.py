"""Public interface for the dataset brick."""
import hashlib
from pathlib import Path
from .runtime.definition_models import DefinitionArtifact, DefinitionArtifactPublishResult, DefinitionArtifactRef
from .runtime.definition_service import dataset_publish_definition_artifact, dataset_resolve_definition_artifact
from .runtime.contracts import (
    DatasetArtifactRef, DatasetExecutionPolicy, DatasetGenerationRequest, DatasetInputRef,
    DatasetJobReceipt, DatasetJobStatus, DatasetManifest, DatasetSnapshotRef,
    DatasetToolSchemaSnapshotRef,
)
from .runtime.can_graph_projection import project_can_graph as dataset_project_can_graph
from .runtime.can_terminal_models import CanTerminalRequest
from .runtime.can_terminal_service import CanTerminalService
from .runtime.can_intelligence import (
    inspect_failure_pattern as dataset_inspect_failure_pattern,
    list_failure_patterns as dataset_list_failure_patterns,
    query_dbc_catalog as dataset_query_dbc_catalog,
    resolve_dbc_candidate as dataset_resolve_dbc_candidate,
)
from .runtime.dbc_identity import dbc_message_identity, dbc_signal_identity, dbc_version_identity
from .runtime.dbc_semantics import DbcMessageDefinition, DbcSignalDefinition, DbcVersionDefinition, DecodedSignalObservation, SemanticRoleBinding
from .runtime.trajectory_landing import DEFAULT_TRAJECTORY_LANDING_ROOT, TRAJECTORY_ROW_SCHEMA_VERSION, TrajectoryRow, TrajectoryRowError, resolve_trajectory_zone, trajectory_zone_path, trajectory_zone_uri, validate_trajectory_row, validate_trajectory_rows
from .runtime.local import LocalDatasetExecutor, LocalDatasetStore
from .runtime.recipe import resolve_recipe
from .runtime.scenario_models import ScenarioPack, ScenarioPackDraft, ScenarioPackGenerationInput, ScenarioPackLineage, ScenarioPackPublishResult, ScenarioPackRef
from .runtime.scenario_store import LocalScenarioPackStore
from .runtime.blueprint_catalog import DETERMINISTIC_TEMPLATE_REF, GENERIC_SCHEMA_REF, SCENARIO_EVIDENCE_DESCRIPTOR, SCENARIO_RECIPE_REF, SCENARIO_STAGE_REF, FixtureReferenceRegistry
from .runtime.blueprint_codec import approval_digest, blueprint_binding
from .runtime.blueprint_models import (
    DatasetBlueprint, DatasetHumanApprovalRecord, DatasetHumanApprovalRef, DatasetQualityPolicyRef, DatasetSourceEvidenceRef,
)
from .runtime.blueprint_results import DatasetBlueprintMaterialization, DatasetBlueprintValidation
from .runtime.blueprint_validation import DatasetBlueprintValidator, require_submission_authority
from .runtime.blueprint_service import DatasetBlueprintService
from .runtime.adapters.blueprint_config import (
    ConfiguredHumanApprovalRegistry, ConfiguredQualityPolicyRegistry,
)
def _store(storage_root: Path | None = None) -> LocalDatasetStore:
    return LocalDatasetStore(storage_root or Path(".dataset_store"))


def dataset_publish_scenario_pack(
    draft: ScenarioPackDraft, storage_root: Path | None = None,
) -> ScenarioPackPublishResult:
    """Validate and immutably publish a canonical ScenarioPack."""
    return LocalScenarioPackStore(storage_root or Path(".dataset_store")).publish(draft)


def dataset_get_scenario_pack(
    ref: ScenarioPackRef, storage_root: Path | None = None,
) -> ScenarioPack:
    """Load and verify a canonical ScenarioPack from its typed reference."""
    return LocalScenarioPackStore(
        storage_root or Path(".dataset_store"), create=False,
    ).load(ref)


def dataset_validate_blueprint(
    blueprint: DatasetBlueprint, storage_root: Path | None = None,
) -> DatasetBlueprintValidation:
    """Validate a blueprint and all opaque registered references without writes."""
    root = storage_root or Path(".dataset_store")
    return DatasetBlueprintValidator(
        root, FixtureReferenceRegistry(),
        ConfiguredQualityPolicyRegistry.from_environment(),
    ).validate(blueprint)


def dataset_materialize_blueprint(
    blueprint: DatasetBlueprint, approval: DatasetHumanApprovalRef,
    storage_root: Path | None = None,
) -> DatasetBlueprintMaterialization:
    """Human-gate a blueprint, then submit it through the existing job path."""
    root = storage_root or Path(".dataset_store")
    validation = dataset_validate_blueprint(blueprint, root)
    published, request = DatasetBlueprintService(
        root, FixtureReferenceRegistry(),
        ConfiguredHumanApprovalRegistry.from_environment(),
    ).prepare(blueprint, approval, validation.binding)
    if published.status == "conflict":
        return DatasetBlueprintMaterialization(
            status="conflict", conflict=published.conflict,
        )
    assert published.ref is not None and request is not None
    receipt = dataset_submit_generation(request, root)
    return DatasetBlueprintMaterialization(
        status="queued", blueprint=published.ref, job_id=receipt.job_id,
        submitted_at=receipt.submitted_at,
    )


def dataset_cancel_job(
    job_id: str, reason: str = "cancelled", storage_root: Path | None = None
) -> DatasetJobStatus:
    """Transition a non-terminal dataset job to failed."""
    return _store(storage_root).cancel_job(job_id, reason)


def dataset_submit_generation(
    request: DatasetGenerationRequest, storage_root: Path | None = None
) -> DatasetJobReceipt:
    """Durably accept a dataset generation request without waiting for execution."""
    require_submission_authority(request, storage_root or Path(".dataset_store"))
    resolve_recipe(request)
    store = _store(storage_root)
    receipt, created = store.create_or_get_job(request)
    if created:
        LocalDatasetExecutor(store.root).submit(receipt.job_id)
    return receipt


def dataset_materialize_can_training_bundle(
    request: CanTerminalRequest, storage_root: Path | None = None,
) -> dict:
    """Run or replay one synchronous, attempt-bound CAN materialization."""
    return CanTerminalService(storage_root or Path(".dataset_store")).materialize(request)


def dataset_get_job(job_id: str, storage_root: Path | None = None) -> DatasetJobStatus | None:
    """Get the durable state of a submitted dataset generation job."""
    return _store(storage_root).get_job(job_id)


def dataset_get_artifact(job_id: str, storage_root: Path | None = None) -> DatasetArtifactRef | None:
    """Get the immutable artifact reference once a job has completed."""
    return _store(storage_root).get_artifact(job_id)


def dataset_resolve_artifact(
    dataset_uri: str, storage_root: Path | None = None
) -> DatasetManifest | None:
    """Resolve an immutable dataset URI to its reproducibility manifest."""
    return _store(storage_root).resolve_manifest(dataset_uri)


def dataset_resolve_trajectory_zone(
    dataset_uri: str, storage_root: Path | None = None
) -> dict:
    """Resolve a digest-verified trajectory landing-zone rowset."""
    return resolve_trajectory_zone(dataset_uri, storage_root)


async def start_dataset_generation(
    config_path: str, storage_root: Path | None = None
) -> str:
    """Deprecated compatibility wrapper for the former config-path API."""
    config = Path(config_path)
    inputs = []
    recipe_uri = "recipe://local/pass-through@1"
    recipe_digest = hashlib.sha256(recipe_uri.encode()).hexdigest()
    compat_root = (storage_root or Path(".dataset_store")) / "compat_snapshots"
    compat_root.mkdir(parents=True, exist_ok=True)

    def _compat_snapshot(label: str, content: bytes) -> DatasetSnapshotRef:
        digest = hashlib.sha256(content).hexdigest()
        snapshot_path = compat_root / f"{label}-{digest}.json"
        if snapshot_path.exists():
            if snapshot_path.read_bytes() != content:
                raise ValueError(f"Immutable compatibility snapshot already exists with different content: {snapshot_path}")
        else:
            snapshot_path.write_bytes(content)
            snapshot_path.chmod(0o444)
        return DatasetSnapshotRef(uri=snapshot_path.resolve().as_uri(), digest=digest)

    if config.exists():
        config_content = config.read_bytes()
        context_snapshot = _compat_snapshot("context", config_content)
    else:
        context_snapshot = _compat_snapshot("context", config_path.encode())

    tool_schema_snapshot = DatasetToolSchemaSnapshotRef(
        uri=_compat_snapshot("tool-schema", b'{"source":"legacy-compat"}').uri,
        digest=hashlib.sha256(b'{"source":"legacy-compat"}').hexdigest(),
        allowed_tools=[],
    )
    if config.exists():
        from .runtime.contracts import DatasetInputRef
        from .runtime.helpers import _sha256

        inputs = [DatasetInputRef(uri=config.resolve().as_uri(), digest=_sha256(config.read_bytes()))]
    receipt = dataset_submit_generation(
        DatasetGenerationRequest(
            recipe_uri=recipe_uri,
            recipe_digest=recipe_digest,
            input_artifacts=inputs,
            context_snapshot=context_snapshot,
            tool_schema_snapshot=tool_schema_snapshot,
        ),
        storage_root,
    )
    return receipt.job_id


async def check_dataset_status(job_id: str, storage_root: Path | None = None) -> dict:
    """Deprecated compatibility wrapper returning the legacy status dictionary."""
    status = dataset_get_job(job_id, storage_root)
    if status is None:
        return {"status": "not_found", "job_id": job_id}
    result = status.model_dump(mode="json")
    return result
