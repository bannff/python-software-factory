"""Deterministic sealed local Chronos backbone fixtures."""
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="Chronos fixtures require the ml group")
chronos = pytest.importorskip("chronos", reason="Chronos fixtures require the ml group")
chronos_config = pytest.importorskip("chronos.chronos2.config")
chronos_model = pytest.importorskip("chronos.chronos2.model")
Chronos2Pipeline = chronos.Chronos2Pipeline
Chronos2CoreConfig = chronos_config.Chronos2CoreConfig
Chronos2Model = chronos_model.Chronos2Model

from factory.machine_learning.runtime.adapters.chronos_identity import MODEL_REVISION
from factory.machine_learning.runtime.adapters.chronos_pipeline import save_backbone
from factory.machine_learning.runtime.chronos_acquisition import validate_chronos_backbone_ref
from factory.machine_learning.runtime.chronos_acquisition_evidence import (
    ACQUISITION_FILENAME,
    acquisition_document,
)
from factory.machine_learning.runtime.passport_config import resolve_chronos_roots
from factory.machine_learning.runtime.passport_tree_seal import seal_read_only_tree
from factory.machine_learning.runtime.passport_trees import chronos_backbone_artifact_ref
from factory.machine_learning.runtime.passport_validation import canonical_json
from factory.machine_learning.runtime.ports import (
    TimeSeriesLoRAConfig,
    TimeSeriesModelConfig,
)


def sealed_chronos_model_config(
    passport_root: Path, *, lora: bool = False,
) -> TimeSeriesModelConfig:
    """Build a tiny seeded backbone in the exact trusted digest namespace."""
    roots = resolve_chronos_roots(passport_root)
    with torch.random.fork_rng():
        torch.manual_seed(0)
        model = Chronos2Model(Chronos2CoreConfig(
            d_model=2, d_kv=2, d_ff=4, num_layers=1, num_heads=1,
            dropout_rate=0.0,
            chronos_config={
                "context_length": 10, "output_patch_size": 2,
                "input_patch_size": 2, "input_patch_stride": 2,
                "quantiles": [0.1, 0.5, 0.9],
            },
        ))
    model.config._commit_hash = MODEL_REVISION
    pipeline = Chronos2Pipeline(model)
    staging = roots.backbone_root / ".fixture.staging"
    save_backbone(pipeline, staging)
    document = acquisition_document(MODEL_REVISION)
    (staging / ACQUISITION_FILENAME).write_bytes(canonical_json(document))
    provisional = chronos_backbone_artifact_ref(
        "backbone", staging, roots.trust_root,
    )
    destination = roots.backbone_root / provisional.digest
    staging.rename(destination)
    ref = chronos_backbone_artifact_ref("backbone", destination, roots.trust_root)
    seal_read_only_tree(destination)
    validate_chronos_backbone_ref(ref, roots.trust_root)
    return TimeSeriesModelConfig(
        local_backbone_ref=ref,
        lora=lora,
        lora_config=TimeSeriesLoRAConfig() if lora else None,
    )


__all__ = ["sealed_chronos_model_config"]
