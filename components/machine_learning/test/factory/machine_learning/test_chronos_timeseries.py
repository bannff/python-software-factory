"""Public authoring and operational Chronos-2 training contracts."""
from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("torch", reason="optional ML extras: uv sync --group ml")
pytest.importorskip("chronos", reason="optional ML extras: uv sync --group ml")

from factory.machine_learning.interface import (  # noqa: E402
    PassportArtifactRef, TimeSeriesLoRAConfig, TimeSeriesModelConfig,
    TimeSeriesModelType, TrackingRuntime, create_server,
)
from factory.machine_learning.runtime import chronos_acquisition  # noqa: E402
from factory.machine_learning.runtime.adapters import chronos_timeseries  # noqa: E402
from factory.machine_learning.runtime.adapters.chronos_identity import (  # noqa: E402
    MODEL_REVISION,
)
from factory.machine_learning.runtime.chronos_acquisition import (  # noqa: E402
    validate_chronos_backbone_ref,
)
from factory.machine_learning.runtime.passport_trees import (  # noqa: E402
    chronos_backbone_artifact_ref,
)


class _Config:
    _commit_hash = MODEL_REVISION


class _Model:
    config = _Config()


class _Pipeline:
    inner_model = _Model()


_Model.__module__, _Model.__name__ = "chronos.chronos2.model", "Chronos2Model"
_Pipeline.__module__, _Pipeline.__name__ = (
    "chronos.chronos2.pipeline", "Chronos2Pipeline",
)


def _tool(server: Any, name: str) -> Any:
    return asyncio.run(server.get_tool(name))


def _install_public_acquisition_stubs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(chronos_acquisition, "acquire_training_pipeline", _Pipeline)

    def save(_pipeline: object, path: Path) -> None:
        path.mkdir(parents=True)
        (path / "config.json").write_text("{}")
        (path / "model.safetensors").write_bytes(b"weights")

    monkeypatch.setattr(chronos_acquisition, "save_backbone", save)
    monkeypatch.setattr(chronos_acquisition, "load_local_pipeline", lambda _path: object())


def _public_acquire(
    root: Path, monkeypatch: pytest.MonkeyPatch,
) -> PassportArtifactRef:
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", "1")
    _install_public_acquisition_stubs(monkeypatch)
    runtime = TrackingRuntime({"model_passport_root": str(root)})
    result = _tool(create_server(runtime), "ml_acquire_chronos2_backbone").fn()
    assert result.ok
    assert result.data is not None
    ref = PassportArtifactRef.model_validate(result.data.artifact)
    validate_chronos_backbone_ref(ref, root)
    return ref


def _install_training_stubs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[Any, ...]]:
    calls: list[tuple[Any, ...]] = []
    monkeypatch.setattr(
        chronos_acquisition, "acquire_training_pipeline",
        lambda: pytest.fail("operational training must not access the Hub"),
    )
    monkeypatch.setattr(chronos_timeseries, "load_local_pipeline", lambda _path: object())

    def train_probe(*args: Any) -> tuple[object, dict[str, float], dict[str, Any]]:
        calls.append(args)
        return object(), {"accuracy": 1.0, "auroc": 1.0}, {
            "d_model": 2, "input_size": 1, "num_classes": 2,
            "scaler_mean": [0.0], "scaler_scale": [1.0],
            "adapter_mode": "lora" if args[-2] else "frozen",
            "lora_config": None, "val_y_true": [0.0],
            "val_y_pred": [0.0], "val_y_score": [0.25],
        }

    def save_probe(root: Path, *_args: Any, **_kwargs: Any) -> None:
        (root / "probe").mkdir()
        (root / "probe" / "probe.pt").write_bytes(b"probe")

    def publish(staging: Path, root: Path) -> Path:
        destination = root / staging.name.removeprefix(".").removesuffix(".staging")
        staging.rename(destination)
        return destination

    monkeypatch.setattr(chronos_timeseries, "train_probe", train_probe)
    monkeypatch.setattr(chronos_timeseries, "save_probe", save_probe)
    monkeypatch.setattr(chronos_timeseries, "seal_content_addressed", publish)
    return calls


def test_authoring_disabled_fails_before_hub(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ML_ENABLE_AUTHORING_TOOLS", raising=False)
    monkeypatch.setattr(
        chronos_acquisition, "acquire_training_pipeline",
        lambda: pytest.fail("Hub must not be touched when authoring is disabled"),
    )
    runtime = TrackingRuntime({"model_passport_root": str(tmp_path)})
    result = _tool(create_server(runtime), "ml_acquire_chronos2_backbone").fn()
    assert not result.ok
    assert result.error is not None
    assert result.error


@pytest.mark.parametrize("lora", [False, True])
def test_public_training_threads_sealed_ref_and_typed_lora(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, lora: bool,
) -> None:
    ref = _public_acquire(tmp_path / "passport", monkeypatch)
    calls = _install_training_stubs(monkeypatch)
    lightgbm_root = tmp_path / "lightgbm"
    runtime = TrackingRuntime({
        "model_passport_root": str(tmp_path / "passport"),
        "lightgbm_model_root": str(lightgbm_root),
    })
    monkeypatch.setattr(
        "factory.machine_learning.mcp.timeseries_tools.persist_training_run",
        lambda *_args, **_kwargs: None,
    )
    model_config: dict[str, Any] = {
        "local_backbone_ref": ref.model_dump(mode="json"), "lora": lora,
    }
    if lora:
        model_config["lora_config"] = TimeSeriesLoRAConfig().model_dump(mode="json")
    before = {key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "KMP_DUPLICATE_LIB_OK")}
    result = _tool(create_server(runtime), "ml_train_timeseries").fn(
        model_type="chronos", X_uri="unused-X", y_uri="unused-y", model_config=model_config,
    )
    assert result.ok
    assert result.data is not None
    assert result.data.status == "completed"
    assert Path(result.data.model_path).is_relative_to(tmp_path / "passport" / "models" / "chronos-2")
    assert not (lightgbm_root / "chronos-2").exists()
    assert calls[0][-2] is lora
    assert (calls[0][-1] is not None) is lora
    assert before == {
        key: os.environ.get(key) for key in ("OMP_NUM_THREADS", "KMP_DUPLICATE_LIB_OK")
    }


@pytest.mark.parametrize("failure", ["missing", "tampered", "unsealed"])
def test_invalid_backbone_ref_fails_before_local_load(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str,
) -> None:
    root = tmp_path / "passport"
    ref = _public_acquire(root, monkeypatch)
    source = Path(ref.uri.removeprefix("file://"))
    if failure == "missing":
        for path in source.iterdir():
            path.chmod(0o600)
        source.chmod(0o700)
        for path in source.iterdir():
            path.unlink()
        source.rmdir()
    elif failure == "tampered":
        target = source / "config.json"
        target.chmod(0o600)
        target.write_text('{"tampered":true}')
    else:
        for path in source.iterdir():
            path.chmod(0o600)
        source.chmod(0o700)
    monkeypatch.setattr(
        chronos_timeseries, "load_local_pipeline",
        lambda _path: pytest.fail("invalid refs must fail before local model load"),
    )
    runtime = TrackingRuntime({"model_passport_root": str(root)})
    with pytest.raises((FileNotFoundError, ValueError)):
        runtime.get_timeseries_trainer().train(
            model_type=TimeSeriesModelType.chronos, X_uri="unused", y_uri="unused",
            model_config=TimeSeriesModelConfig(local_backbone_ref=ref),
        )
