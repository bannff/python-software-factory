"""Machine learning brick - experiment tracking and fine-tuning.

This brick provides a unified interface for experiment tracking and
fine-tuning job management across multiple backends.

Usage:
    from factory.machine_learning import (
        create_experiment, start_run, log_params, log_metrics, end_run
    )

    # Experiment tracking
    exp = create_experiment("my-experiment")
    run = start_run(exp.id, "baseline-run")
    log_params(run.id, {"learning_rate": 0.01})
    log_metrics(run.id, {"accuracy": 0.95})
    end_run(run.id)
"""

from .interface import (
    ExperimentTracker,
    Experiment,
    Run,
    Metric,
    Dataset,
    TrackerHealth,
    FineTuningPort,
    DatasetResolverPort,
    DatasetTrainingInput,
    ResolvedTrainingDataset,
    FineTuningMethod,
    JobStatus,
    LoRAConfig,
    TrainingConfig,
    FineTuningJob,
    Checkpoint,
    ModelArtifact,
    TrackingRuntime,
    get_runtime,
    reset_runtime,
    # Time-series training
    TimeSeriesModelType,
    TimeSeriesTrainingConfig,
    TimeSeriesTrainingJob,
    TimeSeriesTrainingPort,
    # JSONL → NPY bridge
    convert_jsonl_to_npy,
    inspect_jsonl_windows,
    load_jsonl_windows,
    windows_to_arrays,
    # Keystone CAN pipeline
    run_keystone_pipeline,
)
from .core import (
    create_experiment,
    get_experiment,
    list_experiments,
    start_run,
    end_run,
    get_run,
    log_params,
    log_metrics,
    register_dataset,
    get_dataset,
)

__all__ = [
    "ExperimentTracker",
    "Experiment",
    "Run",
    "Metric",
    "Dataset",
    "TrackerHealth",
    "FineTuningPort",
    "DatasetResolverPort",
    "DatasetTrainingInput",
    "ResolvedTrainingDataset",
    "FineTuningMethod",
    "JobStatus",
    "LoRAConfig",
    "TrainingConfig",
    "FineTuningJob",
    "Checkpoint",
    "ModelArtifact",
    "TrackingRuntime",
    "get_runtime",
    "reset_runtime",
    "create_experiment",
    "get_experiment",
    "list_experiments",
    "start_run",
    "end_run",
    "get_run",
    "log_params",
    "log_metrics",
    "register_dataset",
    "get_dataset",
    # Time-series training
    "TimeSeriesModelType",
    "TimeSeriesTrainingConfig",
    "TimeSeriesTrainingJob",
    "TimeSeriesTrainingPort",
    # JSONL → NPY bridge
    "convert_jsonl_to_npy",
    "inspect_jsonl_windows",
    "load_jsonl_windows",
    "windows_to_arrays",
    # Keystone CAN pipeline
    "run_keystone_pipeline",
]
