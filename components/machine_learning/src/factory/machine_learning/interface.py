"""Public interface for machine_learning brick."""

from .server import create_mcp_server as create_server
from .runtime.ports import (
    CanLifecycleStore,
    DatasetResolverPort,
    ExperimentTracker,
    Experiment,
    Run,
    Metric,
    Dataset,
    TrackerHealth,
    FineTuningPort,
    ModelPassportConformanceRunnerPort,
    ModelPassportStorePort,
    ModelPassportVerifierPort,
    TimeSeriesGenerationPort,
    TimeSeriesLoRAConfig,
    TimeSeriesModelConfig,
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
    TimeSeriesTrainingPort,
)
from .runtime.models import (
    CheckpointType,
    DatasetTrainingInput,
    FineTuningMethod,
    JobStatus,
    LoRAConfig,
    TrainingConfig,
    TrainingObjective,
    FineTuningJob,
    Checkpoint,
    ModelArtifact,
    ResolvedTrainingDataset,
)
from .runtime.runtime import TrackingRuntime, get_runtime, reset_runtime
from .runtime.adapters.checkpoint_store import CheckpointStore
from .runtime.adapters.jsonl_to_npy import (
    convert_jsonl_to_npy,
    inspect_jsonl_windows,
    load_jsonl_windows,
    windows_to_arrays,
)
from .runtime.adapters.legacy_can_conversion import legacy_can_windows_to_arrays
from .runtime.can_keystone import run_keystone_pipeline
from .runtime.can_feature_contract import (
    CanDatasetArtifactRef, CanFeatureContract, CanFillPolicy,
    create_can_feature_contract, load_can_feature_contract,
    save_can_feature_contract,
)
from .runtime.can_materializer import CanMaterializedBatch, materialize_can_windows
from .runtime.model_passport import (
    ConformanceEvidence, ModelPassport, ModelPassportBody,
)
from .runtime.passport_codec import create_model_passport, load_model_passport
from .runtime.passport_refs import (
    AdapterBinding, ArchitectureBinding, InferenceBinding, PassportArtifactRef,
    PassportPredecessorRef, PreparationBinding, ScenarioLineageBinding,
)
from .runtime.passport_composition import (
    get_model_passport, get_model_passport_by_model,
)
from .runtime.passport_service import ModelPassportService
from .runtime.can_lifecycle_composition import (
    CanLifecycleOperations, create_can_lifecycle,
)
from .runtime.passport_store_models import (
    ModelPassportConflictError, ModelPassportIntegrityError,
    ModelPassportPublication, ModelPassportRef, ModelPassportRevisionError,
)

ml_get_model_passport = get_model_passport
ml_get_model_passport_by_model = get_model_passport_by_model


def __getattr__(name: str):  # pragma: no cover - exercised indirectly
    """Lazy export — ``CanInferenceBridge`` imports ``joblib`` at module
    level, so an eager import here breaks brick lazy-loading in
    environments without the optional ML extras. Deferred until first
    attribute access (same pattern as ``runtime.adapters.__getattr__``).
    """
    if name == "CanInferenceBridge":
        from .runtime.adapters.can_inference import CanInferenceBridge
        return CanInferenceBridge
    # TimeGAN adapters (Phase 3 hybrid injection) stay deferred so the
    # optional Torch dependency is loaded only when generation is requested.
    if name == "TimeGANAdapter":
        from .runtime.adapters.timegan import TimeGANAdapter
        return TimeGANAdapter
    if name == "ConditionalTimeGANAdapter":
        from .runtime.adapters.timegan_conditional import ConditionalTimeGANAdapter
        return ConditionalTimeGANAdapter
    if name in ("assign_failure_modes", "build_scaria_labels", "DEFAULT_MODE_NAMES"):
        from .runtime.adapters.scania_label_builder import (
            DEFAULT_MODE_NAMES, assign_failure_modes, build_scaria_labels,
        )
        return {
            "DEFAULT_MODE_NAMES": DEFAULT_MODE_NAMES,
            "assign_failure_modes": assign_failure_modes,
            "build_scaria_labels": build_scaria_labels,
        }[name]
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    "CanInferenceBridge",
    "CanLifecycleOperations",
    "CanLifecycleStore",
    "CheckpointStore",
    "CheckpointType",
    "ExperimentTracker",
    "Experiment",
    "Run",
    "Metric",
    "Dataset",
    "TrackerHealth",
    "FineTuningPort",
    "ModelPassportConformanceRunnerPort",
    "ModelPassportService",
    "ModelPassportStorePort",
    "ModelPassportVerifierPort",
    "DatasetResolverPort",
    "DatasetTrainingInput",
    "ResolvedTrainingDataset",
    "FineTuningMethod",
    "JobStatus",
    "LoRAConfig",
    "TrainingConfig",
    "TrainingObjective",
    "FineTuningJob",
    "Checkpoint",
    "ModelArtifact",
    "TimeSeriesModelType",
    "TimeSeriesTrainingConfig",
    "TimeSeriesTrainingJob",
    "TimeSeriesTrainingPort",
    "TimeSeriesGenerationPort",
    "TimeSeriesLoRAConfig",
    "TimeSeriesModelConfig",
    "TrackingRuntime",
    "get_runtime",
    "reset_runtime",
    "create_server",
    "create_can_lifecycle",
    # JSONL → NPY bridge
    "convert_jsonl_to_npy",
    "inspect_jsonl_windows",
    "load_jsonl_windows",
    "windows_to_arrays",
    "legacy_can_windows_to_arrays",
    # Keystone CAN pipeline + immutable feature contract
    "run_keystone_pipeline",
    "CanDatasetArtifactRef", "CanFeatureContract", "CanFillPolicy",
    "CanMaterializedBatch", "create_can_feature_contract",
    "load_can_feature_contract", "materialize_can_windows",
    "save_can_feature_contract",
    # Generic immutable model passports
    "AdapterBinding", "ArchitectureBinding", "ConformanceEvidence",
    "InferenceBinding", "ModelPassport", "ModelPassportBody",
    "ModelPassportConflictError", "ModelPassportIntegrityError",
    "ModelPassportPublication", "ModelPassportRef", "ModelPassportRevisionError",
    "PassportArtifactRef", "PassportPredecessorRef", "PreparationBinding",
    "ScenarioLineageBinding", "create_model_passport", "get_model_passport",
    "get_model_passport_by_model", "load_model_passport",
    "ml_get_model_passport", "ml_get_model_passport_by_model",
    # Phase 3 hybrid injection (SCANIA → TimeGAN). Lazy-resolved via
    # ``__getattr__`` because the adapters import torch at module level.
    "TimeGANAdapter",
    "ConditionalTimeGANAdapter",
    "assign_failure_modes",
    "build_scaria_labels",
    "DEFAULT_MODE_NAMES",
]
