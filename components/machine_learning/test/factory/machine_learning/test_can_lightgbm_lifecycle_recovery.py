"""Request-bound LightGBM seal and ambiguous-completion recovery tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.local_can_lifecycle import LocalCanLifecycleStore
from factory.machine_learning.runtime.can_feature_contract import save_can_feature_contract
from factory.machine_learning.runtime.can_lifecycle_canonical import effect_identity
from factory.machine_learning.runtime.training_lifecycle_coordinator import CanLifecycleContext
from factory.machine_learning.runtime.can_lightgbm_operation import (
    execute_lightgbm, reconcile_lightgbm, train_portfolio,
)
from factory.machine_learning.runtime.can_model_evaluation import canonical_input_digest
from factory.machine_learning.runtime.passport_tree_seal import remove_staging_tree
from factory.machine_learning.runtime.ports import TimeSeriesTrainingConfig

from .can_contract_fixtures import contract

_EVAL_METRICS = {
    "accuracy": 0.8, "precision": 0.7, "recall": 0.7, "f1": 0.7,
    "auroc": 0.8, "auprc": 0.7, "brier": 0.2,
}


def _evaluate(**kwargs):
    return {
        "schema": "evals.can-model-evidence", "version": "1.0",
        "evaluator_identity": "evals.can-model@v1",
        "input_digest": canonical_input_digest(**kwargs),
        "metrics": dict(_EVAL_METRICS),
    }


def _ref(path: Path) -> dict:
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"uri": path.as_uri(), "sha256": digest, "evidence": {"sha256": digest}}


@pytest.fixture
def training(tmp_path: Path):
    data = tmp_path / "data"
    data.mkdir()
    value = contract(data)
    contract_path = data / "contract.json"
    save_can_feature_contract(value, contract_path)
    rng = np.random.default_rng(42)
    X = rng.normal(size=(120, value.required_width)).astype(np.float32)
    y = (X[:, 0] + X[:, 1] > 0).astype(np.int64)
    x_path, y_path = data / "X.npy", data / "y.npy"
    np.save(x_path, X); np.save(y_path, y)
    root = tmp_path / "models"
    refs = {"contract": _ref(contract_path), "x_2d": _ref(x_path), "y": _ref(y_path)}
    yield root, refs, TimeSeriesTrainingConfig(window_size=2, seed=17)
    remove_staging_tree(root)


def _execute(training, effect_id="a" * 64, *, rank=1, experiment="sealed-exp"):
    root, refs, config = training
    return execute_lightgbm(
        effect_id, refs, root, None, config, experiment, "0x1", rank, _evaluate,
    )


def _reconcile(training, effect_id="a" * 64, *, rank=1, experiment="sealed-exp"):
    root, refs, config = training
    return reconcile_lightgbm(
        effect_id, refs, root, config, experiment, "0x1", rank, _evaluate,
    )


def test_execute_seals_complete_tree_and_reconcile_is_byte_equivalent(training):
    executed = _execute(training)
    seal_path = Path(executed["artifact_seal"]["uri"].removeprefix("file://"))
    model_path = Path(executed["model_path"])
    assert seal_path.exists() and not (seal_path.stat().st_mode & 0o222)
    assert not (model_path.stat().st_mode & 0o222)
    assert _reconcile(training) == executed


def test_reconcile_rejects_partial_and_tampered_seals(training):
    root, _, _ = training
    partial = root / ("b" * 64) / "mlflow-model"
    partial.mkdir(parents=True)
    with pytest.raises(ValueError, match="partial"):
        _reconcile(training, "b" * 64)
    result = _execute(training)
    seal_path = Path(result["artifact_seal"]["uri"].removeprefix("file://"))
    seal_path.chmod(0o644)
    value = json.loads(seal_path.read_bytes())
    value["rank"] = 99
    seal_path.write_text(json.dumps(value, sort_keys=True, separators=(",", ":")))
    seal_path.chmod(0o444)
    with pytest.raises(ValueError, match="seal digest mismatch"):
        _reconcile(training)


def test_reconcile_rejects_substituted_valid_native_model(training):
    first = _execute(training, "c" * 64, experiment="first")
    second = _execute(training, "d" * 64, experiment="second")
    first_tree, second_tree = Path(first["model_path"]), Path(second["model_path"])
    remove_staging_tree(first_tree.parent)
    shutil.copytree(second_tree.parent, first_tree.parent)
    with pytest.raises(ValueError, match="exact request"):
        _reconcile(training, "c" * 64, experiment="first")


def test_reconcile_rejects_valid_seal_for_different_intent(training):
    _execute(training, "e" * 64, rank=2, experiment="bound")
    with pytest.raises(ValueError, match="exact request"):
        _reconcile(training, "e" * 64, rank=1, experiment="bound")
    with pytest.raises(ValueError, match="exact request"):
        _reconcile(training, "e" * 64, rank=2, experiment="substituted")


def test_initial_lifecycle_training_seals_and_receipt_replays(training):
    root, refs, _ = training
    terminal = {"training_bundle": {
        "top_can_ids": ["0x1"], "training_artifacts_by_can_id": {"0x1": refs},
    }}
    context = CanLifecycleContext("train@v1", "f" * 64, LocalCanLifecycleStore(root))
    first = train_portfolio(
        context, dataset_terminal=terminal, root=root, tracker=None,
        evaluator=_evaluate, config={"window_size": 2, "seed": 17},
        experiment_name="lifecycle", top_n=1,
    )
    assert Path(first[0]["artifact_seal"]["uri"].removeprefix("file://")).exists()
    replay = train_portfolio(
        CanLifecycleContext("train@v1", "f" * 64, LocalCanLifecycleStore(root)),
        dataset_terminal=terminal, root=root, tracker=None, evaluator=_evaluate,
        config={"window_size": 2, "seed": 17},
        experiment_name="lifecycle", top_n=1,
    )
    assert replay == first


def test_ambiguous_completed_tree_is_adopted_without_refit(training, monkeypatch):
    root, refs, config = training
    request_sha = "1" * 64
    effect_id = effect_identity("train@v1", request_sha, "train-lightgbm:0x1@v1")
    expected = _execute(training, effect_id, experiment="adopt")
    terminal = {"training_bundle": {
        "top_can_ids": ["0x1"], "training_artifacts_by_can_id": {"0x1": refs},
    }}
    import factory.machine_learning.runtime.can_lightgbm_operation as operation
    monkeypatch.setattr(
        operation, "execute_lightgbm",
        lambda *_args, **_kwargs: pytest.fail("valid sealed tree must not refit"),
    )
    adopted = train_portfolio(
        CanLifecycleContext("train@v1", request_sha, LocalCanLifecycleStore(root)),
        dataset_terminal=terminal, root=root, tracker=None, evaluator=_evaluate,
        config={"window_size": config.window_size, "seed": config.seed},
        experiment_name="adopt", top_n=1,
    )
    assert adopted == [expected]


def test_reconcile_rejects_tampered_model_tree(training):
    result = _execute(training, "2" * 64, experiment="tampered-tree")
    model_file = Path(result["model_path"]) / "model.lgb"
    model_file.chmod(0o600)
    model_file.write_bytes(model_file.read_bytes() + b"\n# tampered\n")
    model_file.chmod(0o400)
    with pytest.raises(ValueError, match="exact request"):
        _reconcile(training, "2" * 64, experiment="tampered-tree")


def test_valid_sibling_staging_is_finalized_without_refit(training):
    root, _, _ = training
    effect_id = "3" * 64
    expected = _execute(training, effect_id, experiment="staged")
    final = root / effect_id
    staging = root / f".{effect_id}.staging"
    final.rename(staging)
    adopted = _reconcile(training, effect_id, experiment="staged")
    assert adopted == expected
    assert final.exists() and not staging.exists()
    assert Path(adopted["model_path"]).is_relative_to(final)


def test_partial_staging_is_removed_before_refit(training):
    root, _, _ = training
    effect_id = "4" * 64
    staging = root / f".{effect_id}.staging"
    staging.mkdir(parents=True)
    (staging / "partial").write_text("incomplete")
    assert _reconcile(training, effect_id, experiment="partial") is None
    assert not staging.exists()
    completed = _execute(training, effect_id, experiment="partial")
    assert Path(completed["model_path"]).is_relative_to(root / effect_id)


def test_final_paths_never_reference_staging(training):
    result = _execute(training, "5" * 64, experiment="final-paths")
    assert ".staging" not in result["model_path"]
    assert ".staging" not in result["artifact_seal"]["uri"]


@pytest.mark.parametrize("phase", [
    "before-native", "after-native-seal", "after-tree-seal", "after-publication",
])
def test_crash_boundaries_recover_with_exactly_one_completed_fit(
    training, monkeypatch: pytest.MonkeyPatch, phase: str,
):
    import factory.machine_learning.runtime.can_lightgbm_operation as operation

    root, refs, config = training
    request_sha = hashlib.sha256(phase.encode()).hexdigest()
    unit = "train-lightgbm:0x1@v1"
    calls = {"fit": 0, "crash": 0}
    original_train = operation.train_lightgbm

    def counted_train(*args, **kwargs):
        if phase == "before-native" and calls["crash"] == 0:
            calls["crash"] += 1
            raise KeyboardInterrupt("crash before native completion")
        calls["fit"] += 1
        return original_train(*args, **kwargs)

    monkeypatch.setattr(operation, "train_lightgbm", counted_train)
    target_name = {
        "after-native-seal": "seal_lightgbm_artifact",
        "after-tree-seal": "fsync_tree",
        "after-publication": "finalize",
    }.get(phase)
    if target_name:
        original = getattr(operation, target_name)

        def crash_after(*args, **kwargs):
            result = original(*args, **kwargs)
            if calls["crash"] == 0:
                calls["crash"] += 1
                raise KeyboardInterrupt(f"crash at {phase}")
            return result

        monkeypatch.setattr(operation, target_name, crash_after)

    def invoke():
        context = CanLifecycleContext(
            "ml.train-can-portfolio@v1", request_sha, LocalCanLifecycleStore(root),
        )
        return context.effect(
            unit,
            {"refs": refs, "config": {"window_size": 2, "seed": 17}},
            lambda effect_id: reconcile_lightgbm(
                effect_id, refs, root, config, "crash", "0x1", 1, _evaluate,
            ),
            lambda effect_id: execute_lightgbm(
                effect_id, refs, root, None, config, "crash", "0x1", 1, _evaluate,
            ),
        )

    with pytest.raises(KeyboardInterrupt, match="crash"):
        invoke()
    recovered = invoke()
    assert recovered["job_id"] == effect_identity(
        "ml.train-can-portfolio@v1", request_sha, unit,
    )
    assert calls == {"fit": 1, "crash": 1}
