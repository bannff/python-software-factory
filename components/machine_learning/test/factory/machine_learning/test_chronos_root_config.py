"""Chronos durable-root composition and fail-closed contracts."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from factory.machine_learning.interface import TrackingRuntime
from factory.machine_learning.runtime.passport_config import resolve_chronos_roots


@pytest.mark.parametrize("source", ["service", "config", "env"])
def test_runtime_captures_root_once_with_precedence(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, source: str,
) -> None:
    roots = {name: tmp_path / name for name in ("service", "config", "env")}
    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", str(roots["env"]))
    service = SimpleNamespace(storage_root=roots["service"] if source == "service" else None)
    config = {"model_passport_root": roots["config"]} if source != "env" else {}
    runtime = TrackingRuntime(config, passport_service=service)
    expected = roots[source].absolute()

    service.storage_root = tmp_path / "late-service"
    config["model_passport_root"] = tmp_path / "late-config"
    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", str(tmp_path / "late-env"))
    assert runtime.chronos_storage_root() == expected


def test_runtime_without_root_still_supports_non_chronos(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ML_MODEL_PASSPORT_ROOT", raising=False)
    runtime = TrackingRuntime()
    assert runtime.chronos_storage_root() is None
    assert runtime.get_tracker("memory").health_check().healthy is True


def test_direct_chronos_calls_never_recover_root_from_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    pytest.importorskip("torch", reason="optional ML extras")
    pytest.importorskip("chronos", reason="optional ML extras")
    from factory.machine_learning.runtime import chronos_acquisition
    from factory.machine_learning.runtime.adapters.chronos_timeseries import (
        ChronosTimeSeriesAdapter,
    )

    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", str(tmp_path / "env-root"))
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", "1")
    monkeypatch.setattr(
        chronos_acquisition, "acquire_training_pipeline",
        lambda: pytest.fail("missing root must fail before Hub acquisition"),
    )
    with pytest.raises(ValueError, match="explicit non-null storage root"):
        resolve_chronos_roots(None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="explicit non-null storage root"):
        ChronosTimeSeriesAdapter(storage_root=None)  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="explicit non-null storage root"):
        chronos_acquisition.acquire_chronos2_backbone(None)  # type: ignore[arg-type]
    assert not (tmp_path / "env-root").exists()
