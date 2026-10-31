"""Exact-ref MCP authority tests for promoted neural ModelPassports."""
from __future__ import annotations

import asyncio
import hashlib
import inspect
from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("torch", reason="neural passport tests require the ml group")
pytest.importorskip("ncps.torch", reason="neural passport tests require the ml group")
pytest.importorskip("chronos", reason="neural passport tests require the ml group")
pytest.importorskip("peft", reason="neural passport tests require the ml group")

from factory.machine_learning.runtime import passport_native_inference as native
from factory.machine_learning.runtime.adapters.patchtst_timeseries import PatchTSTTimeSeriesAdapter
from factory.machine_learning.runtime.adapters.torch_timeseries import TorchTimeSeriesAdapter
from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.passport_native_inference import load_neural_passport_scores
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service

from .lnn_passport_fixtures import lnn_passport_case
from .test_neural_passport_subprocess import _candidate


@pytest.fixture
def promoted(tmp_path: Path, request):
    previous = get_service("tool_invoker")
    model_type = getattr(request, "param", TimeSeriesModelType.lstm)
    root, passport, candidate, X, warm = _candidate(tmp_path, model_type)
    service = create_local_passport_service(root)
    publication = service.verify_and_promote(candidate.ref)
    value = service.get(publication.ref)
    try:
        yield root, service, passport, candidate.ref, publication.ref, value, X, warm
    finally:
        set_service("tool_invoker", previous)


def _tool(runtime: TrackingRuntime, service):
    server = create_mcp_server(runtime=runtime, passport_service=service)
    return asyncio.run(server.get_tool("ml_predict_neural_passport")).fn


def _invoke(tool, ref, X_uri: str, **timing: str) -> dict:
    return tool(
        X_uri=X_uri, model_id=ref.model_id, model_version=ref.model_version,
        passport_revision=ref.passport_revision, passport_uri=ref.uri,
        passport_digest=ref.digest, **timing,
    )


@pytest.mark.parametrize(
    "promoted",
    [TimeSeriesModelType.lstm, TimeSeriesModelType.tcn, TimeSeriesModelType.patchtst],
    indirect=True,
)
def test_mcp_cold_scores_exact_ref_without_warm_cache(promoted) -> None:
    root, service, _, _, ref, _, _, warm = promoted
    runtime = TrackingRuntime(passport_service=service)
    tool = _tool(runtime, service)
    parameters = inspect.signature(tool).parameters
    assert {"passport", "model_path"}.isdisjoint(parameters)
    assert runtime._inference_registry == {} and runtime._inference_bridges == {}
    result = _invoke(tool, ref, str(root / "scoring-X.npy"))
    assert result.ok and result.data is not None
    assert result.data.status == "completed"
    assert np.array_equal(np.asarray(result.data.y_score), warm)
    assert result.data.count == len(warm)
    assert runtime._inference_registry == {} and runtime._inference_bridges == {}


def test_mcp_rejects_candidate_unregistered_bad_digest_and_stale_refs(promoted) -> None:
    root, service, _, candidate_ref, ref, _, _, _ = promoted
    tool = _tool(TrackingRuntime(passport_service=service), service)
    invalid = (
        candidate_ref,
        ref.model_copy(update={"model_id": "unregistered"}),
        ref.model_copy(update={"digest": "0" * 64}),
        ref.model_copy(update={"passport_revision": 1}),
    )
    for bad_ref in invalid:
        result = _invoke(tool, bad_ref, str(root / "X.npy"))
        assert not result.ok and result.data is None
    bad_x = root / "bad-X.npy"
    np.save(bad_x, np.zeros((2, 9, 2), dtype=np.float32))
    assert not _invoke(tool, ref, str(bad_x)).ok
    supplied = _invoke(
        tool, ref, str(root / "X.npy"),
        live_timing_uri=(root / "X.npy").as_uri(),
        live_timing_digest="0" * 64,
    )
    assert not supplied.ok and supplied.data is None
    assert "not accepted" in supplied.error


def test_service_scorer_rejects_no_root_and_stale_predecessor(promoted) -> None:
    root, service, _, _, ref, value, X, _ = promoted

    class NoRoot:
        storage_root = None

        def get(self, requested):
            return service.get(requested)

    with pytest.raises(ValueError, match="durable root"):
        load_neural_passport_scores(NoRoot(), ref, X)

    class StalePredecessor:
        storage_root = str(root)

        def get(self, requested):
            if requested == ref:
                return value
            raise ValueError("stale predecessor")

    with pytest.raises(ValueError, match="stale predecessor"):
        load_neural_passport_scores(StalePredecessor(), ref, X)


def test_tamper_fails_before_native_scoring(promoted, monkeypatch) -> None:
    _, service, _, _, ref, value, X, _ = promoted
    calls: list[bool] = []
    monkeypatch.setattr(native, "_load_scores", lambda *args: calls.append(True))
    path = Path(value.model_artifact.uri.removeprefix("file://"))
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="exact bytes"):
        load_neural_passport_scores(service, ref, X)
    assert calls == []


@pytest.mark.parametrize(
    ("adapter_type", "model_type", "env_name"),
    [
        (TorchTimeSeriesAdapter, TimeSeriesModelType.lstm, "TORCH_TS_MODEL_DIR"),
        (PatchTSTTimeSeriesAdapter, TimeSeriesModelType.patchtst, "PATCHTST_TS_MODEL_DIR"),
    ],
)
def test_deployable_neural_training_requires_durable_root(
    adapter_type, model_type, env_name: str, monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(env_name, raising=False)
    adapter = adapter_type()
    with pytest.raises(ValueError, match="model_root"):
        adapter.train(model_type, "missing-X.npy", "missing-y.npy")


def test_mcp_lnn_requires_valid_live_timing_without_training_comparison(
    lnn_passport_case,
) -> None:
    case = lnn_passport_case
    service = create_local_passport_service(case["root"])
    ref = service.verify_and_promote(case["publication"].ref).ref
    runtime = TrackingRuntime(passport_service=service)
    assert runtime._inference_registry == {} and runtime._inference_bridges == {}
    tool = _tool(runtime, service)
    live_x = case["X"][:7]
    live_timing = case["timing"][:7] * 1.25
    x_path = case["root"] / "live-X.npy"
    timing_path = case["root"] / "live-timing.npy"
    np.save(x_path, live_x)
    np.save(timing_path, live_timing)
    digest = hashlib.sha256(timing_path.read_bytes()).hexdigest()

    omitted = _invoke(tool, ref, str(x_path))
    assert not omitted.ok and omitted.data is None
    assert "requires live timing" in omitted.error
    result = _invoke(
        tool, ref, str(x_path), live_timing_uri=timing_path.as_uri(),
        live_timing_digest=digest,
    )
    assert result.ok and result.data is not None
    assert result.data.status == "completed"
    assert result.data.live_timing.model_dump() == {"digest": digest, "shape": [7, 10]}

    equal_rows_path = case["root"] / "equal-rows-live-timing.npy"
    np.save(equal_rows_path, case["timing"] * 1.25)
    equal_rows_digest = hashlib.sha256(equal_rows_path.read_bytes()).hexdigest()
    equal_rows = _invoke(
        tool, ref, str(case["root"] / "X.npy"),
        live_timing_uri=equal_rows_path.as_uri(),
        live_timing_digest=equal_rows_digest,
    )
    assert equal_rows.ok and equal_rows.data is not None
    assert equal_rows.data.status == "completed"
    assert equal_rows.data.live_timing.shape == [20, 10]

    equal_digest = _invoke(
        tool, ref, str(case["root"] / "X.npy"),
        live_timing_uri=case["timing_path"].as_uri(),
        live_timing_digest=case["candidate"].preparation.timespans.digest,
    )
    assert equal_digest.ok and equal_digest.data is not None
    assert equal_digest.data.status == "completed"
    assert runtime._inference_registry == {} and runtime._inference_bridges == {}
