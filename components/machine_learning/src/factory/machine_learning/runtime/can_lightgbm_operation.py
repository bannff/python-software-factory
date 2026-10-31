"""Deterministic LightGBM training with Evals-owned held-out metrics."""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

from .adapters.mlflow_lightgbm import load_lightgbm_flavor, validate_lightgbm_flavor
from .adapters.sklearn_lightgbm import load_array, train_lightgbm
from .can_dataset_binding import exact_training_refs
from .can_feature_contract import load_can_feature_contract
from .can_lightgbm_publication import effect_paths, finalize, fsync_tree
from .can_lightgbm_seal import seal_lightgbm_artifact, verify_lightgbm_artifact
from .can_model_evaluation import (
    CanEvaluator, EVALUATOR_TOOL, EVALUATOR_TOOL_IDENTITY, evaluate_holdout,
)
from .passport_tree_seal import (
    remove_staging_tree, require_read_only_tree, seal_read_only_tree,
)
from .ports import TimeSeriesTrainingConfig


def train_portfolio(
    context: Any, *, dataset_terminal: dict[str, Any], root: Path,
    tracker: Any, evaluator: CanEvaluator, config: dict[str, Any],
    experiment_name: str, top_n: int,
) -> list[dict[str, Any]]:
    """Train selected CAN IDs with stable request-bound effect identities."""
    cfg = TimeSeriesTrainingConfig(**config)
    ids = list(dataset_terminal["training_bundle"]["top_can_ids"])[:top_n]
    if not ids:
        raise ValueError("Dataset training bundle contains no CAN-IDs")
    rows = []
    for rank, can_id in enumerate(ids, start=1):
        refs = exact_training_refs(dataset_terminal, can_id)
        inputs = {
            "can_id": can_id, "rank": rank, "refs": refs,
            "config": asdict(cfg), "experiment_name": experiment_name,
            "evaluator": EVALUATOR_TOOL_IDENTITY,
        }
        rows.append(context.effect(
            f"train-lightgbm:{can_id}@v1", inputs,
            lambda effect_id: reconcile_lightgbm(
                effect_id, refs, root, cfg, experiment_name, can_id, rank, evaluator,
            ),
            lambda effect_id: execute_lightgbm(
                effect_id, refs, root, tracker, cfg, experiment_name, can_id, rank,
                evaluator,
            ),
        ))
    return rows


def execute_lightgbm(
    effect_id: str, refs: dict[str, dict[str, Any]], root: Path, tracker: Any,
    config: TimeSeriesTrainingConfig, experiment_name: str, can_id: str, rank: int,
    evaluator: CanEvaluator,
) -> dict[str, Any]:
    """Fit beneath a sibling staging tree, seal, fsync, then rename atomically."""
    root.mkdir(parents=True, exist_ok=True)
    final, staging = effect_paths(root, effect_id)
    if final.exists() or final.is_symlink():
        output = _verify_effect(
            final, effect_id, refs, root, config, experiment_name, can_id, rank,
            evaluator,
        )
        remove_staging_tree(staging)
        return output
    remove_staging_tree(staging)
    staging.mkdir(mode=0o700)
    try:
        job, _ = train_lightgbm(
            tracker=tracker, root=root, effect_dir=staging,
            x_uri=refs["x_2d"]["uri"], y_uri=refs["y"]["uri"], config=config,
            experiment_name=experiment_name, job_id=effect_id,
        )
        model_path = staging / "mlflow-model"
        validate_lightgbm_flavor(model_path)
        seal_lightgbm_artifact(
            model_path, root, effect_id=effect_id, refs=refs,
            config=asdict(config), can_id=can_id, rank=rank,
            experiment_name=experiment_name, effect_dir=staging,
        )
        seal_read_only_tree(staging)
        fsync_tree(staging)
        finalize(staging, final, root)
    except Exception:
        remove_staging_tree(staging)
        raise
    return _verify_effect(
        final, job.id, refs, root, config, experiment_name, can_id, rank, evaluator,
    )


def reconcile_lightgbm(
    effect_id: str, refs: dict[str, dict[str, Any]], root: Path,
    config: TimeSeriesTrainingConfig, experiment_name: str, can_id: str, rank: int,
    evaluator: CanEvaluator,
) -> dict[str, Any] | None:
    """Adopt exact final/staging trees; remove partial staging before refit."""
    final, staging = effect_paths(root, effect_id)
    if final.exists() or final.is_symlink():
        output = _verify_effect(
            final, effect_id, refs, root, config, experiment_name, can_id, rank,
            evaluator,
        )
        remove_staging_tree(staging)
        return output
    if not (staging.exists() or staging.is_symlink()):
        return None
    try:
        _verify_effect(
            staging, effect_id, refs, root, config, experiment_name, can_id, rank,
            evaluator,
        )
    except Exception:
        try:
            seal_read_only_tree(staging)
            fsync_tree(staging)
            _verify_effect(
                staging, effect_id, refs, root, config, experiment_name, can_id, rank,
                evaluator,
            )
        except Exception:
            remove_staging_tree(staging)
            return None
    finalize(staging, final, root)
    return _verify_effect(
        final, effect_id, refs, root, config, experiment_name, can_id, rank, evaluator,
    )


def _verify_effect(
    effect_dir, effect_id, refs, root, config, experiment, can_id, rank, evaluator,
):
    model_path = effect_dir / "mlflow-model"
    seal_path = effect_dir / "lightgbm-artifact-seal.json"
    if not model_path.exists() or not seal_path.exists():
        raise ValueError("LightGBM lifecycle artifact is partial")
    require_read_only_tree(effect_dir)
    validate_lightgbm_flavor(model_path)
    seal = verify_lightgbm_artifact(
        model_path, root, effect_id=effect_id, refs=refs, config=asdict(config),
        can_id=can_id, rank=rank, experiment_name=experiment, effect_dir=effect_dir,
    )
    X, y = load_array(refs["x_2d"]["uri"]), load_array(refs["y"]["uri"]).ravel()
    model = load_lightgbm_flavor(model_path, expected_width=X.shape[1])
    metrics, evidence, provenance = evaluate_holdout(X, y, model, config, evaluator)
    return _output(
        effect_id, str(model_path), metrics, evidence, provenance,
        refs, can_id, rank, config, seal,
    )


def _output(
    job_id, model_path, metrics, evidence, provenance,
    refs, can_id, rank, config, seal,
):
    contract = load_can_feature_contract(refs["contract"]["uri"])
    if contract.can_id != can_id:
        raise ValueError("Dataset feature contract ref disagrees with its CAN-ID")
    X = np.load(Path(refs["x_2d"]["uri"].removeprefix("file://")), allow_pickle=False)
    y = np.load(Path(refs["y"]["uri"].removeprefix("file://")), allow_pickle=False)
    label_dist = {str(label): int(np.count_nonzero(y == label)) for label in (0, 1)}
    return {
        "rank": rank, "can_id": can_id, "model_family": "lightgbm",
        "job_id": job_id, "model_path": model_path, "metrics": metrics,
        "evaluation_evidence": evidence,
        "evaluator_provenance": provenance.model_dump(mode="json"),
        "training_config": asdict(config),
        "artifact_refs": refs, "artifact_seal": seal, "n_samples": int(len(y)),
        "label_dist": label_dist, "window_size": int(contract.required_shape[0]),
        "n_features": int(contract.required_shape[1]),
        "x_shape": list(X.shape), "contract_digest": contract.digest,
    }


__all__ = [
    "EVALUATOR_TOOL", "EVALUATOR_TOOL_IDENTITY", "execute_lightgbm",
    "reconcile_lightgbm", "train_portfolio",
]
