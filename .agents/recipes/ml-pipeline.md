# Recipe: ML Pipeline

Validates experiment tracking and fine-tuning against an immutable dataset artifact.

## Bricks Used
- `machine_learning` - Experiment tracking, fine-tuning, and model registry
- `dataset` - Dataset generation and artifact resolution
- `storage` - Storing model artifacts
- `telemetry` - Tracing ML operations

## Dataset Handoff

Dataset generation is owned by the `dataset` brick. Once a dataset job completes, resolve its artifact and construct the ML-owned value object:

```python
from factory.machine_learning.runtime.models import DatasetTrainingInput

training_input = DatasetTrainingInput(
    dataset_uri=artifact.dataset_uri,
    manifest_uri=artifact.manifest_uri,
    dataset_digest=artifact.digest,
    view_name="sft",
    view_schema_version=manifest.view_schema_versions["sft"],
)
```

## Fine-Tuning

```python
from factory.machine_learning.runtime.models import FineTuningMethod, LoRAConfig, TrainingConfig

job = finetuner.create_job(
    method=FineTuningMethod.lora,
    base_model="bert-base-uncased",
    training_input=training_input,
    training_config=TrainingConfig(epochs=5, batch_size=16, learning_rate=2e-5),
    lora_config=LoRAConfig(rank=8, alpha=16, dropout=0.1),
)
job = finetuner.start_job(job.id)
```

The ML brick does not expose dataset generator tools, stage-output paths, or a raw `dataset_ref` compatibility field. Backends must receive a resolver-provided training location before they launch.

## Tracking and Checkpoints

Use `get_tracker()` for experiments, runs, params, metrics, and dataset registration. Use `get_checkpoint_store()` and the fine-tuning adapter for training checkpoints, model exports, and cleanup.

## Success Criteria

- Experiment history is queryable.
- The typed dataset input is preserved through the fine-tuning lifecycle.
- Dataset digest, manifest URI, view, and schema version remain attached to ML lineage.
- Unresolved dataset artifacts fail closed before a backend process starts.
