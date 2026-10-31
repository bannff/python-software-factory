"""Independent native-LTC passport acceptance fixture."""
from __future__ import annotations

import hashlib
from pathlib import Path

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.lnn_timeseries import LnnTimeSeriesAdapter
from factory.machine_learning.runtime.adapters.temporal_split import (
    temporal_split_with_shuffle_fallback,
)
from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract
from factory.machine_learning.runtime.can_passports import CanPassportContext, issue_can_model_passport
from factory.machine_learning.runtime.passport_artifacts import file_artifact_ref
from factory.machine_learning.runtime.ports import (
    TimeSeriesModelConfig, TimeSeriesModelType, TimeSeriesTrainingConfig,
)
from factory.mcp_utils.interface import get_service, set_service

from .can_contract_fixtures import contract


def _dataset(root: Path, name: str) -> tuple[Path, Path]:
    data = root / "artifacts" / name / f"{name}.jsonl"
    data.parent.mkdir(parents=True, exist_ok=True)
    data.write_text('{"value":1}\n')
    raw = f'{{"name":"{name}"}}'.encode()
    manifest = root / "manifests" / f"manifest-{hashlib.sha256(raw).hexdigest()}.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_bytes(raw)
    return data, manifest


@pytest.fixture
def lnn_passport_case(tmp_path: Path):
    """Train one real LTC and issue its exact revision-one candidate."""
    previous = get_service("tool_invoker")
    root, dataset_root = tmp_path / "passports", tmp_path / "datasets"
    root.mkdir()
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
        root, num_timesteps=10, window_size_ms=100,
        step_size_ms=100, observation_cutoff_ms=100,
    )
    contract_uri = save_can_feature_contract(value, root / "contract.json")
    rng = np.random.default_rng(17)
    X = rng.normal(size=(20, 10, 2)).astype(np.float32)
    y = (X[:, :, 0].mean(axis=1) > 0).astype(np.int64)
    timing = rng.uniform(1.0, 100.0, size=(20, 10)).astype(np.float64)
    x_path, y_path, timing_path = root / "X.npy", root / "y.npy", root / "timing.npy"
    np.save(x_path, X); np.save(y_path, y); np.save(timing_path, timing)
    adapter = LnnTimeSeriesAdapter(model_root=root / "models")
    job = adapter.train(
        TimeSeriesModelType.lnn, str(x_path), str(y_path),
        TimeSeriesTrainingConfig(
            window_size=10, batch_size=8, epochs=1, early_stopping_patience=1,
        ),
        model_config=TimeSeriesModelConfig(
            auxiliary_uris={"timespans": timing_path.as_uri()},
        ),
    )
    validation = np.concatenate([X, timing[..., None]], axis=-1)
    _, _, validation, _ = temporal_split_with_shuffle_fallback(
        validation, y, job.config.validation_split, job.config.seed,
    )
    validation_X = validation[..., :X.shape[-1]].copy()
    validation_timing = validation[..., X.shape[-1]].copy()
    warm_uri = adapter.predict(job.id, str(x_path))
    warm = np.load(warm_uri.removeprefix("file://"))
    passport, publication = issue_can_model_passport(
        context=CanPassportContext(tuple(lineage), None, str(root)),
        job=job, row={"metrics": job.metrics}, model_type="lnn",
        x_uri=x_path.as_uri(), y_uri=y_path.as_uri(),
        info={"n_samples": 20, "window_size": 10, "n_features": 2,
              "timespans_uri": timing_path.as_uri()},
        contract_uri=contract_uri, contract=value,
    )
    try:
        yield {
            "root": root, "X": X, "timing": timing, "timing_path": timing_path,
            "validation_X": validation_X, "validation_timing": validation_timing,
            "job": job, "warm": warm, "candidate": passport,
            "publication": publication,
        }
    finally:
        set_service("tool_invoker", previous)


__all__ = ["lnn_passport_case"]
