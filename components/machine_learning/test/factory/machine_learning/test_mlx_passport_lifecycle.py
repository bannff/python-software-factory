"""MLX lifecycle acceptance from native training through passport MCP scoring."""
from __future__ import annotations

import asyncio
import json
import stat
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from pydantic import ValidationError

pytest.importorskip("mlx.core", reason="native MLX acceptance requires Apple Silicon")
pytest.importorskip("chronos", reason="neural passport helpers require mlx-test")
pytest.importorskip("peft", reason="neural passport helpers require mlx-test")

from factory.machine_learning.runtime.adapters.mlx_identity import MLX_LIFECYCLE
from factory.machine_learning.runtime.adapters import mlx_platform
from factory.machine_learning.runtime.mlx_publication import require_mlx_reference
from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.passport_native_inference import load_neural_passport_scores
from factory.machine_learning.runtime.ports import TimeSeriesModelType, TimeSeriesTrainingJob
from factory.machine_learning.runtime.runtime import TrackingRuntime
from factory.machine_learning.runtime.timeseries_identity import TimeSeriesLifecycleIdentity
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service

from .neural_passport_candidate import neural_candidate
from .neural_passport_subprocess_support import FRESH_NEURAL_SCORE_SCRIPT


@pytest.mark.parametrize(("system", "machine", "installed", "message"), [
    ("Linux", "arm64", "0.31.1", "Darwin arm64"),
    ("Darwin", "x86_64", "0.31.1", "Darwin arm64"),
    ("Darwin", "arm64", "0.31.0", "version drift"),
])
def test_platform_guard_is_exact_before_mlx_use(
    monkeypatch: pytest.MonkeyPatch, system: str, machine: str,
    installed: str, message: str,
) -> None:
    monkeypatch.setattr(mlx_platform.platform, "system", lambda: system)
    monkeypatch.setattr(mlx_platform.platform, "machine", lambda: machine)
    monkeypatch.setattr(mlx_platform, "version", lambda _: installed)
    with pytest.raises(RuntimeError, match=message):
        mlx_platform.require_mlx_platform()


def test_mlx_lifecycle_identity_is_strict_and_frozen() -> None:
    assert MLX_LIFECYCLE.framework_version == "0.31.1"
    with pytest.raises(ValidationError):
        TimeSeriesLifecycleIdentity.model_validate({
            **MLX_LIFECYCLE.model_dump(), "framework_version": 0.311,
        })
    with pytest.raises(ValidationError, match="frozen"):
        MLX_LIFECYCLE.framework_version = "0.31.0"  # type: ignore[misc]
    job = TimeSeriesTrainingJob(
        id="mlx", model_type=TimeSeriesModelType.lstm,
        lifecycle_identity=MLX_LIFECYCLE,
    )
    assert job.backend == "mlx" and job.framework_version == "0.31.1"
    with pytest.raises(AttributeError, match="frozen"):
        job.lifecycle_identity = None


def test_mlx_training_job_rejects_untyped_lifecycle_identity() -> None:
    with pytest.raises(TypeError, match="TimeSeriesLifecycleIdentity"):
        TimeSeriesTrainingJob(
            id="mlx", model_type=TimeSeriesModelType.lstm,
            lifecycle_identity={"backend": "mlx"},  # type: ignore[arg-type]
        )


def test_mlx_runtime_rejects_caller_selected_storage_root(tmp_path: Path) -> None:
    runtime = TrackingRuntime({"model_passport_root": str(tmp_path / "authority")})
    with pytest.raises(ValueError, match="runtime composition"):
        runtime.get_timeseries_trainer(
            "mlx", storage_root=tmp_path / "caller-selected",
        )


@pytest.mark.parametrize("model_type", [TimeSeriesModelType.lstm, TimeSeriesModelType.tcn])
def test_mlx_candidate_promotes_and_mcp_fresh_scores_match(
    tmp_path: Path, model_type: TimeSeriesModelType,
) -> None:
    previous = get_service("tool_invoker")
    try:
        root, candidate, publication, X, warm = neural_candidate(
            tmp_path, model_type, backend="mlx",
        )
        reference = Path(candidate.model_artifact.uri.removeprefix("file://"))
        tree, digest = require_mlx_reference(reference, candidate.model_artifact.digest)
        assert reference.parent == root / "models" / "mlx"
        assert reference.name == candidate.model_artifact.digest == digest
        assert reference.is_file() and tree.name.startswith(".")
        assert tree.parent == reference.parent and tree.name != digest
        assert candidate.model_artifact.format == "mlx-safetensors"
        assert {item.name for item in tree.iterdir()} == {
            "factory_model.json", "model.safetensors",
        }
        assert all(not item.stat().st_mode & stat.S_IWUSR for item in (tree, *tree.iterdir()))
        assert candidate.architecture.framework == "mlx"
        assert candidate.inference.loader == MLX_LIFECYCLE.loader

        service = create_local_passport_service(root)
        promoted_ref = service.verify_and_promote(publication.ref).ref
        promoted = service.get(promoted_ref)
        assert promoted.passport_revision == 2
        assert promoted.conformance_evidence[0].verifier_identity == MLX_LIFECYCLE.verifier_identity
        cold = load_neural_passport_scores(service, promoted_ref, X)[:, 1]
        np.testing.assert_array_equal(warm, cold)

        live_x = root / "mlx-live-X.npy"
        np.save(live_x, X)
        runtime = TrackingRuntime(passport_service=service)
        server = create_mcp_server(runtime=runtime, passport_service=service)
        tool = asyncio.run(server.get_tool("ml_predict_neural_passport")).fn
        result = tool(
            X_uri=str(live_x), model_id=promoted_ref.model_id,
            model_version=promoted_ref.model_version,
            passport_revision=promoted_ref.passport_revision,
            passport_uri=promoted_ref.uri, passport_digest=promoted_ref.digest,
        )
        assert result.ok and result.data is not None
        assert result.data.status == "completed"
        np.testing.assert_array_equal(np.asarray(result.data.y_score), warm)
        assert runtime._inference_registry == {} and runtime._inference_bridges == {}

        completed = subprocess.run(
            [sys.executable, "-c", FRESH_NEURAL_SCORE_SCRIPT], check=True,
            input=json.dumps({
                "root": str(root), "ref": promoted_ref.model_dump(mode="json"),
                "x": str(live_x),
            }), text=True, capture_output=True,
        )
        fresh = np.asarray(json.loads(completed.stdout))[:, 1]
        np.testing.assert_array_equal(cold, fresh)
    finally:
        set_service("tool_invoker", previous)


def test_platform_guard_rejects_missing_mlx(monkeypatch: pytest.MonkeyPatch) -> None:
    from importlib.metadata import PackageNotFoundError

    monkeypatch.setattr(mlx_platform.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mlx_platform.platform, "machine", lambda: "arm64")

    def missing(_: str) -> str:
        raise PackageNotFoundError("mlx")

    monkeypatch.setattr(mlx_platform, "version", missing)
    with pytest.raises(RuntimeError, match="not installed"):
        mlx_platform.require_mlx_platform()
