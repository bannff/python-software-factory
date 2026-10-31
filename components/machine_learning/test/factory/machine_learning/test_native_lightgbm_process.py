"""Failure-containment contract for the native LightGBM subprocess port."""
from __future__ import annotations

import json
from pathlib import Path
import sys

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.native_lightgbm_process import (
    NativeProcessError, SubprocessNativeLightGBM,
)
from factory.machine_learning.runtime.adapters.sklearn_lightgbm import train_lightgbm
from factory.machine_learning.runtime.adapters.transfer_learning import TransferLearningManager
from factory.machine_learning.runtime.native_lightgbm_contracts import (
    ArtifactPayload, InspectRequest,
)
from factory.machine_learning.runtime.ports import TimeSeriesTrainingConfig


def _request(tmp_path: Path) -> InspectRequest:
    return InspectRequest(
        operation="inspect_joblib",
        payload=ArtifactPayload(source=str(tmp_path / "missing.joblib")),
    )


def _command(monkeypatch: pytest.MonkeyPatch, runner, script: str) -> None:
    monkeypatch.setattr(runner, "_command", lambda: [sys.executable, "-c", script])


def test_sigsegv_is_contained_and_parent_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = SubprocessNativeLightGBM(timeout_seconds=2)
    _command(monkeypatch, runner, (
        "import os,signal,sys;sys.stderr.write('unsafe\\npath\\x00');"
        "os.kill(os.getpid(), signal.SIGSEGV)"
    ))
    with pytest.raises(NativeProcessError) as caught:
        runner.execute(_request(tmp_path))
    assert caught.value.code == "native_process_crash"
    assert "signal=" in str(caught.value)
    assert "\n" not in str(caught.value) and "\x00" not in str(caught.value)
    assert 2 + 2 == 4


def test_timeout_kills_process_group_and_parent_survives(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = SubprocessNativeLightGBM(timeout_seconds=0.05)
    _command(monkeypatch, runner, "import time; time.sleep(30)")
    with pytest.raises(NativeProcessError) as caught:
        runner.execute(_request(tmp_path))
    assert caught.value.code == "native_process_timeout"
    assert Path.cwd().exists()


def test_malformed_output_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = SubprocessNativeLightGBM(timeout_seconds=2)
    _command(monkeypatch, runner, "print('{not-json')")
    with pytest.raises(NativeProcessError) as caught:
        runner.execute(_request(tmp_path))
    assert caught.value.code == "native_process_protocol_error"


def test_ordinary_worker_failure_has_stable_code_and_no_retry(tmp_path: Path) -> None:
    runner = SubprocessNativeLightGBM(timeout_seconds=2)
    with pytest.raises(NativeProcessError) as caught:
        runner.execute(_request(tmp_path))
    assert caught.value.code == "native_operation_failed"
    assert "joblib" in str(caught.value).lower()


def test_child_crash_cannot_publish_partial_model(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(4)
    X = rng.normal(size=(40, 4)).astype(np.float32)
    y = (X[:, 0] > 0).astype(np.int64)
    x_path, y_path = tmp_path / "X.npy", tmp_path / "y.npy"
    np.save(x_path, X); np.save(y_path, y)
    script = (
        "import json,os,signal,sys,pathlib;"
        "p=json.loads(sys.stdin.read())['payload'];"
        "d=pathlib.Path(p['destination']);d.mkdir();"
        "(d/'partial').write_text('bad');"
        "os.kill(os.getpid(),signal.SIGSEGV)"
    )
    runner = SubprocessNativeLightGBM(timeout_seconds=2)
    _command(monkeypatch, runner, script)
    root = tmp_path / "models"
    with pytest.raises(NativeProcessError) as caught:
        train_lightgbm(
            tracker=None, root=root, x_uri=str(x_path), y_uri=str(y_path),
            config=TimeSeriesTrainingConfig(), experiment_name="failure",
            job_id="fixed", native_port=runner,
        )
    assert caught.value.code == "native_process_crash"
    assert not (root / "fixed").exists()
    assert not (root / ".fixed.staging").exists()
    assert list(root.iterdir()) == []


def test_semantically_invalid_success_output_fails_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = SubprocessNativeLightGBM(timeout_seconds=2)
    response = {
        "ok": True, "operation": "inspect_joblib",
        "result": {
            "kind": "inspect", "width": 1, "threshold": 0.5,
            "importances": [-1.0],
        },
    }
    _command(monkeypatch, runner, f"print({json.dumps(json.dumps(response))})")
    with pytest.raises(NativeProcessError) as caught:
        runner.execute(_request(tmp_path))
    assert caught.value.code == "native_process_protocol_error"


def test_launch_failure_has_stable_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    import factory.machine_learning.runtime.adapters.native_lightgbm_process as module

    monkeypatch.setattr(
        module.subprocess, "Popen", lambda *_args, **_kwargs: (_ for _ in ()).throw(
            OSError("unsafe\nlaunch")
        ),
    )
    with pytest.raises(NativeProcessError) as caught:
        SubprocessNativeLightGBM(timeout_seconds=2).execute(_request(tmp_path))
    assert caught.value.code == "native_process_crash"
    assert "\n" not in str(caught.value)


def test_transfer_inspection_failure_cannot_publish(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    rng = np.random.default_rng(11)
    X = rng.normal(size=(40, 4)).astype(np.float32)
    y = (X[:, 0] > 0).astype(np.int64)
    manager = TransferLearningManager(tmp_path / "transfer")
    import factory.machine_learning.runtime.adapters.transfer_learning as module

    def fail_inspection(*_args, **_kwargs):
        raise NativeProcessError("native_process_crash", "inspection failed")

    monkeypatch.setattr(module, "load_lightgbm_flavor", fail_inspection)
    with pytest.raises(NativeProcessError) as caught:
        manager.train_with_transfer("lightgbm", X, y, X, y, iteration=1)
    assert caught.value.code == "native_process_crash"
    assert manager.registry["models"] == {}
    assert not (manager.base_dir / "lightgbm_iter1").exists()
    assert not (manager.base_dir / ".lightgbm_iter1.staging").exists()
