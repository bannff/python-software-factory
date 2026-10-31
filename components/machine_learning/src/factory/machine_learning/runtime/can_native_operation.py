"""Effect-idempotent native LNN and Chronos CAN lifecycle training."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .can_dataset_binding import exact_training_refs
from .can_family_specs import family_spec
from .can_feature_contract import load_can_feature_contract
from .can_model_evaluation import evaluate_predictions
from .can_native_record import publish_native_record, replay_native_record
from .ports import TimeSeriesTrainingConfig


def train_native_portfolio(
    context: Any, *, dataset_terminal: dict[str, Any], root: Path,
    trainer: Any, evaluator: Any, family: str, config: dict[str, Any],
    model_config: dict[str, Any] | None, experiment_name: str, top_n: int,
) -> list[dict[str, Any]]:
    """Train native families from exact Dataset refs through the shared port."""
    spec = family_spec(family)
    cfg = TimeSeriesTrainingConfig(**config)
    ids = list(dataset_terminal["training_bundle"]["top_can_ids"])[:top_n]
    if not ids:
        raise ValueError("Dataset training bundle contains no CAN-IDs")
    rows = []
    for rank, can_id in enumerate(ids, start=1):
        refs = exact_training_refs(dataset_terminal, can_id, family)
        resolved_model_config = spec.model_config(refs, model_config)
        binding = {
            "can_id": can_id, "rank": rank, "model_family": family,
            "refs": refs, "training_config": asdict(cfg),
            "model_config": (
                resolved_model_config.model_dump(mode="json")
                if resolved_model_config is not None else None
            ),
            "experiment_name": experiment_name,
        }
        unit = f"train-{family}:{can_id}@v1"
        rows.append(context.effect(
            unit, binding,
            lambda effect_id, b=binding: replay_native_record(root, effect_id, b),
            lambda effect_id, b=binding: _execute(
                effect_id, b, root, trainer, evaluator, spec,
                resolved_model_config, cfg,
            ),
        ))
    return rows


def _execute(effect_id, binding, root, trainer, evaluator, spec, model_config, cfg):
    effective = TimeSeriesTrainingConfig(**{
        **asdict(cfg), "extra": {**cfg.extra, "lifecycle_job_id": effect_id},
    })
    refs = binding["refs"]
    job = trainer.train(
        spec.model_type, refs[spec.x_ref]["uri"], refs["y"]["uri"],
        config=effective, experiment_name=binding["experiment_name"],
        model_config=model_config,
    )
    if job.status != "completed" or job.id != effect_id or not job.model_path:
        raise ValueError("native trainer did not preserve lifecycle effect identity")
    metrics, evidence, provenance = evaluate_predictions(
        job.val_y_true, job.val_y_pred, job.val_y_score, evaluator,
    )
    contract = load_can_feature_contract(refs["contract"]["uri"])
    X = _array(refs[spec.x_ref]["uri"])
    y = _array(refs["y"]["uri"]).ravel()
    if contract.can_id != binding["can_id"] or len(X) != len(y):
        raise ValueError("native Dataset refs disagree with their CAN contract")
    row = {
        "rank": binding["rank"], "can_id": binding["can_id"],
        "model_family": spec.model_type.value, "job_id": job.id,
        "model_path": str(job.model_path), "metrics": metrics,
        "evaluation_evidence": evidence,
        "evaluator_provenance": provenance.model_dump(mode="json"),
        "training_config": asdict(effective),
        "model_config": binding["model_config"], "artifact_refs": refs,
        "n_samples": int(len(y)), "window_size": int(contract.required_shape[0]),
        "n_features": int(contract.required_shape[1]),
        "label_dist": {str(label): int(np.count_nonzero(y == label)) for label in (0, 1)},
        "x_shape": list(X.shape), "contract_digest": contract.digest,
    }
    return publish_native_record(root, effect_id, binding, row)


def _array(uri: str) -> np.ndarray:
    return np.load(Path(uri.removeprefix("file://")), allow_pickle=False)


__all__ = ["train_native_portfolio"]
