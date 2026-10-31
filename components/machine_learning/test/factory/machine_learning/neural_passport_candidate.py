"""Native neural candidate fixture with genuine Chronos trained-object scores."""
import hashlib
from pathlib import Path

import numpy as np

from factory.machine_learning.runtime.adapters.chronos_native import load_scores
from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract
from factory.machine_learning.runtime.can_passports import CanPassportContext, issue_can_model_passport
from factory.machine_learning.runtime.can_passport_models import sealed_config
from factory.machine_learning.runtime.passport_artifacts import file_artifact_ref
from factory.machine_learning.runtime.passport_native_inference import _load_neural_snapshot_scores
from factory.machine_learning.runtime.passport_snapshot import verified_snapshot
from factory.machine_learning.runtime.ports import TimeSeriesModelType, TimeSeriesTrainingConfig
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.mcp_utils.interface import set_service

from .can_contract_fixtures import contract
from .chronos_passport_fixtures import sealed_chronos_model_config
from .neural_passport_subprocess_support import assert_parity


def neural_candidate(
    tmp_path: Path, model_type: TimeSeriesModelType, *, lora: bool = False,
    backend: str | None = None,
):
    """Train, publish, and return candidate data plus genuine warm scores."""
    passport_root, dataset_root = tmp_path / "passports", tmp_path / "datasets"
    passport_root.mkdir()
    lineage, resolved = [], {}
    for prefix in ("training", "synthesis"):
        data, manifest = _dataset(dataset_root, prefix)
        lineage.extend((
            file_artifact_ref(f"{prefix}_dataset", str(data)),
            file_artifact_ref(f"{prefix}_manifest", str(manifest)),
        ))
        resolved[data.as_uri()] = {
            "dataset_uri": data.as_uri(), "manifest_uri": manifest.as_uri(),
            "dataset_digest": hashlib.sha256(data.read_bytes()).hexdigest(),
            "scenario_lineage": None,
        }

    def invoke(name: str, **kwargs):
        assert name == "dataset_resolve_artifact"
        return {
            "schema_version": "v1", "ok": True,
            "data": resolved[kwargs["dataset_uri"]], "error": None,
            "idempotency_key": None,
        }

    set_service("tool_invoker", invoke)
    value = contract(
        passport_root, num_timesteps=10, window_size_ms=100,
        step_size_ms=100, observation_cutoff_ms=100,
    )
    contract_uri = save_can_feature_contract(value, passport_root / "contract.json")
    rng = np.random.default_rng(7)
    X = rng.normal(size=(20, 10, 2)).astype(np.float32)
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    x_path, y_path = passport_root / "X.npy", passport_root / "y.npy"
    np.save(x_path, X)
    np.save(y_path, y)
    model_root = passport_root / "models"
    runtime = TrackingRuntime({
        "model_passport_root": str(passport_root),
        "lightgbm_model_root": str(model_root),
    })
    adapter = runtime.get_timeseries_trainer(backend)
    model_config = (
        sealed_chronos_model_config(passport_root, lora=lora)
        if model_type is TimeSeriesModelType.chronos else None
    )
    job = adapter.train(
        model_type, str(x_path), str(y_path),
        TimeSeriesTrainingConfig(
            window_size=10, batch_size=8, epochs=1, early_stopping_patience=1,
        ),
        model_config=model_config,
    )
    Path(job.model_path).resolve().relative_to(model_root.resolve())
    set_service("tool_invoker", invoke)
    passport, publication = issue_can_model_passport(
        context=CanPassportContext(tuple(lineage), None, str(passport_root)),
        job=job, row={"metrics": job.metrics}, model_type=model_type.value,
        x_uri=x_path.as_uri(), y_uri=y_path.as_uri(),
        info={"n_samples": 20, "window_size": 10, "n_features": 2},
        contract_uri=contract_uri, contract=value,
    )
    from factory.machine_learning.runtime.adapters.temporal_split import (
        temporal_split_with_shuffle_fallback,
    )
    scoring_X = temporal_split_with_shuffle_fallback(
        X, y, job.config.validation_split, job.config.seed,
    )[2]
    np.save(passport_root / "scoring-X.npy", scoring_X)
    with verified_snapshot(passport, passport_root, ("model",)) as snapshot:
        if model_type is TimeSeriesModelType.chronos:
            candidate_scores = load_scores(
                snapshot["model"], sealed_config(passport.architecture.config), scoring_X,
            )[:, 1]
        else:
            candidate_scores = _load_neural_snapshot_scores(
                passport, snapshot["model"], scoring_X,
            )[:, 1]
    warm = np.asarray(job.val_y_score)
    assert warm.ndim == 1 and np.isfinite(warm).all()
    assert len(job.val_y_true) == len(job.val_y_pred) == len(warm) == len(scoring_X)
    assert_parity(
        warm, candidate_scores, passport.architecture.config.get("parity_tolerance"),
    )
    return passport_root, passport, publication, scoring_X, warm


def _dataset(root: Path, name: str) -> tuple[Path, Path]:
    data = root / "artifacts" / name / f"{name}.jsonl"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text('{"value":1}\n')
    raw = f'{{"name":"{name}"}}'.encode()
    manifest = root / "manifests" / f"manifest-{hashlib.sha256(raw).hexdigest()}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(raw)
    return data, manifest


__all__ = ["neural_candidate"]
