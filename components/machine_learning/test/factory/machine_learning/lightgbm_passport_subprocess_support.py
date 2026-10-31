"""Fresh-process scripts and fixtures for LightGBM passport conformance."""
from __future__ import annotations
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

from factory.machine_learning.runtime.adapters.memory_adapter import MemoryTracker
from factory.machine_learning.runtime.adapters.sklearn_timeseries import (
    SklearnTimeSeriesAdapter,
)
from factory.machine_learning.runtime.adapters.temporal_split import (
    temporal_split_with_shuffle_fallback,
)
from factory.machine_learning.runtime.can_feature_contract import (
    save_can_feature_contract,
)
from factory.machine_learning.runtime.can_passports import (
    issue_can_model_passport, resolve_can_passport_context,
)
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import set_service

from .can_contract_fixtures import contract, window

FRESH_PREDICT_SCRIPT = r'''
import asyncio, json, sys
from pathlib import Path
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import set_service
p=json.loads(sys.stdin.read())
def invoke(name, **kwargs):
    if name == "dataset_resolve_artifact":
        assert kwargs["storage_root"] == p["dataset_root"]
        item=p["lineage"][kwargs["dataset_uri"]]
        return {"schema_version":"v1","ok":True,"data":{"dataset_uri":item["dataset_uri"],"manifest_uri":item["manifest_uri"],"dataset_digest":item["digest"],"scenario_lineage":None},"error":None,"idempotency_key":None}
    if name == "dataset_submit_generation":
        Path(p["marker"]).write_text("scored")
        return {"schema_version":"v1","ok":True,"data":{"job_id":"fresh-job"},"error":None,"idempotency_key":None}
    if name == "dataset_get_job": return {"schema_version":"v1","ok":True,"data":{"status":"completed"},"error":None,"idempotency_key":None}
    if name == "dataset_get_artifact": return {"schema_version":"v1","ok":True,"data":{"dataset_uri":p["window_uri"],"manifest_uri":p["manifest_uri"]},"error":None,"idempotency_key":None}
    raise AssertionError(name)
set_service("tool_invoker", invoke)
runtime=TrackingRuntime()
assert runtime._inference_registry == {} and runtime._inference_bridges == {}
tool=asyncio.run(create_mcp_server(runtime=runtime).get_tool("can_predict_failure"))
r=p["ref"]
result=tool.fn(records=p["records"],contract_digest=p["contract_digest"],model_id=r["model_id"],model_version=r["model_version"],passport_revision=r["passport_revision"],passport_uri=r["uri"],passport_digest=r["digest"])
assert runtime._inference_registry == {} and runtime._inference_bridges == {}
print(result.model_dump_json())
'''

FRESH_SCORE_SCRIPT = r'''
import json, sys
from pathlib import Path
import numpy as np
from factory.machine_learning.runtime.adapters.mlflow_lightgbm import load_lightgbm_flavor, validated_probabilities
from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.passport_snapshot import verified_snapshot
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef
from factory.mcp_utils.interface import set_service
p=json.loads(sys.stdin.read())
def invoke(name, **kwargs):
    assert name == "dataset_resolve_artifact"
    assert kwargs["storage_root"] == p["dataset_root"]
    item=p["lineage"][kwargs["dataset_uri"]]
    return {"schema_version":"v1","ok":True,"data":{"dataset_uri":item["dataset_uri"],"manifest_uri":item["manifest_uri"],"dataset_digest":item["digest"],"scenario_lineage":None},"error":None,"idempotency_key":None}
set_service("tool_invoker", invoke)
service=create_local_passport_service(Path(p["root"]))
ref=ModelPassportRef.model_validate(p["ref"])
passport=service.get(ref)
X=np.load(p["x"], allow_pickle=False)
with verified_snapshot(passport, p["root"], ("model",)) as snapshot:
    scores=validated_probabilities(load_lightgbm_flavor(snapshot["model"]), X)[:, 1]
print(json.dumps(scores.tolist()))
'''


def _artifact(root: Path, name: str) -> dict:
    bundle, manifests = root / "artifacts" / name, root / "manifests"
    bundle.mkdir(parents=True, exist_ok=True)
    manifests.mkdir(parents=True, exist_ok=True)
    dataset = bundle / f"dataset-{name}.jsonl"
    dataset.write_text('{"value":1}\n')
    manifest_bytes = f'{{"name":"{name}"}}'.encode()
    manifest = manifests / f"manifest-{hashlib.sha256(manifest_bytes).hexdigest()}.json"
    manifest.write_bytes(manifest_bytes)
    return {
        "dataset_uri": dataset.as_uri(), "manifest_uri": manifest.as_uri(),
        "digest": hashlib.sha256(dataset.read_bytes()).hexdigest(),
    }


def _lineage_invoker(training: dict, synthesis: dict):
    def invoke(name: str, **kwargs):
        if name != "dataset_resolve_artifact":
            raise AssertionError(name)
        item = training if kwargs["dataset_uri"] == training["dataset_uri"] else synthesis
        return {
            "schema_version": "v1", "ok": True,
            "data": {
                "dataset_uri": item["dataset_uri"],
                "manifest_uri": item["manifest_uri"],
                "dataset_digest": item["digest"], "scenario_lineage": None,
            },
            "error": None, "idempotency_key": None,
        }
    return invoke


def candidate(passport_root: Path, dataset_root: Path):
    training = _artifact(dataset_root, "training")
    synthesis = _artifact(dataset_root, "synthesis")
    set_service("tool_invoker", _lineage_invoker(training, synthesis))
    context = resolve_can_passport_context(
        training, synthesis, passport_storage_root=passport_root,
        dataset_storage_root=dataset_root,
    )
    feature_contract = contract(passport_root)
    contract_uri = save_can_feature_contract(
        feature_contract, passport_root / "contract.json",
    )
    rng = np.random.default_rng(17)
    X = rng.normal(size=(80, 4)).astype(np.float32)
    y = (X[:, 0] + X[:, 3] > 0).astype(np.int64)
    x_path, y_path = passport_root / "X.npy", passport_root / "y.npy"
    np.save(x_path, X); np.save(y_path, y)
    trainer = SklearnTimeSeriesAdapter(
        tracker=MemoryTracker(), model_root=passport_root / "models",
    )
    job = trainer.train(TimeSeriesModelType.lightgbm, str(x_path), str(y_path))
    _, _, validation_X, _ = temporal_split_with_shuffle_fallback(
        X, y, job.config.validation_split, job.config.seed,
    )
    validation_path = passport_root / "validation-X.npy"
    np.save(validation_path, validation_X)
    set_service("tool_invoker", _lineage_invoker(training, synthesis))
    passport, publication = issue_can_model_passport(
        context=context, job=job, row={"metrics": job.metrics},
        model_type="lightgbm", x_uri=x_path.as_uri(), y_uri=y_path.as_uri(),
        info={"n_samples": 80, "window_size": 2, "n_features": 2},
        contract_uri=contract_uri, contract=feature_contract,
    )
    return (
        passport, publication, feature_contract, training, synthesis,
        job, validation_path,
    )


def fresh_predict(
    root: Path, dataset_root: Path, ref: dict, feature_contract,
    training: dict, synthesis: dict, marker: Path,
) -> dict:
    windows, manifest = root / "inference-windows.jsonl", root / "inference-manifest.json"
    windows.write_text(json.dumps(window(feature_contract)) + "\n")
    manifest.write_text("{}")
    payload = {
        "root": str(root), "dataset_root": str(dataset_root), "ref": ref,
        "lineage": {training["dataset_uri"]: training, synthesis["dataset_uri"]: synthesis},
        "window_uri": windows.as_uri(), "manifest_uri": manifest.as_uri(),
        "marker": str(marker), "contract_digest": feature_contract.digest,
        "records": [
            {"timestamp_ns": i * 10_000_000, "arbitration_id": "0x1",
             "vehicle_id": "v", "decoded_signals": {"a": i + 1.0, "b": i + 2.0},
             "is_failure": i == 2} for i in range(3)
        ],
    }
    completed = subprocess.run(
        [sys.executable, "-c", FRESH_PREDICT_SCRIPT],
        input=json.dumps(payload), text=True, capture_output=True,
        cwd=Path(__file__).parents[5], check=True,
    )
    return json.loads(completed.stdout)

__all__ = ["FRESH_SCORE_SCRIPT", "candidate", "fresh_predict"]


_LEGACY_JOBLIB_SCRIPT = r'''
import joblib, numpy as np, sys
from lightgbm import LGBMClassifier
X=np.load(sys.argv[1], allow_pickle=False)
y=np.load(sys.argv[2], allow_pickle=False)
model=LGBMClassifier(n_estimators=8, verbose=-1, random_state=3).fit(X,y)
joblib.dump(model.booster_ if sys.argv[4] == "booster" else model, sys.argv[3])
'''


def create_legacy_joblib(path: Path, X: np.ndarray, y: np.ndarray, *, raw_booster: bool = False) -> None:
    """Create a legacy fixture in a fresh process without native parent imports."""
    x_path, y_path = path.with_suffix(".X.npy"), path.with_suffix(".y.npy")
    np.save(x_path, X, allow_pickle=False); np.save(y_path, y, allow_pickle=False)
    try:
        subprocess.run(
            [sys.executable, "-c", _LEGACY_JOBLIB_SCRIPT,
             str(x_path), str(y_path), str(path),
             "booster" if raw_booster else "classifier"],
            check=True, capture_output=True, text=True,
        )
    finally:
        x_path.unlink(missing_ok=True); y_path.unlink(missing_ok=True)
