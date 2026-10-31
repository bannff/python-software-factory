"""Native neural candidate promotion, cold parity, and fail-closed tests."""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="neural passport tests require the ml group")
pytest.importorskip("chronos", reason="neural passport tests require the ml group")
pytest.importorskip("peft", reason="neural passport tests require the ml group")

from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.passport_native_inference import (
    load_neural_passport_scores,
)
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import get_service, set_service

from .neural_passport_candidate import neural_candidate as _candidate
from .neural_passport_subprocess_support import FRESH_NEURAL_SCORE_SCRIPT, assert_parity


@pytest.mark.parametrize(
    "model_type",
    [
        TimeSeriesModelType.lstm,
        TimeSeriesModelType.tcn,
        TimeSeriesModelType.patchtst,
        TimeSeriesModelType.chronos,
    ],
)
def test_native_candidate_promotes_and_fresh_scores_match(
    tmp_path: Path, model_type: TimeSeriesModelType
) -> None:
    previous = get_service("tool_invoker")
    try:
        root, candidate, publication, X, warm = _candidate(tmp_path, model_type)
        assert candidate.promotion_status == "candidate"
        assert candidate.inference.loader in {
            "torch.state_dict",
            "transformers.patchtst",
            "chronos.Chronos2Pipeline",
        }
        service = create_local_passport_service(root)
        promoted_pub = service.verify_and_promote(publication.ref)
        promoted = service.get(promoted_pub.ref)
        assert promoted.passport_revision == 2 and promoted.promotion_status == "promotable"
        model_path = Path(promoted.model_artifact.uri.removeprefix("file://"))
        cold = load_neural_passport_scores(service, promoted_pub.ref, X)[:, 1]
        tolerance = candidate.architecture.config.get("parity_tolerance")
        assert_parity(warm, cold, tolerance)
        completed = subprocess.run(
            [sys.executable, "-c", FRESH_NEURAL_SCORE_SCRIPT],
            check=True,
            input=json.dumps(
                {
                    "root": str(root),
                    "ref": promoted_pub.ref.model_dump(mode="json"),
                    "x": str(root / "scoring-X.npy"),
                }
            ),
            text=True,
            capture_output=True,
        )
        fresh = np.asarray(json.loads(completed.stdout))[:, 1]
        assert_parity(cold, fresh, tolerance)
        target = (
            model_path / "probe" / "probe.pt"
            if model_type is TimeSeriesModelType.chronos
            else (model_path / "factory_preprocessing.json" if model_path.is_dir() else model_path)
        )
        target.chmod(0o600)
        target.write_bytes(target.read_bytes() + b"tamper")
        with pytest.raises(ValueError, match="exact bytes|exact model tree|sealed read-only"):
            load_neural_passport_scores(service, promoted_pub.ref, X)
        with pytest.raises(ValueError, match="exact bytes|exact model tree|sealed read-only"):
            service.get(promoted_pub.ref)
    finally:
        set_service("tool_invoker", previous)


def test_torch_strict_state_scaler_shape_and_framework_failures(tmp_path: Path) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, X, _ = _candidate(tmp_path, TimeSeriesModelType.lstm)
        path = Path(candidate.model_artifact.uri.removeprefix("file://"))
        from factory.machine_learning.runtime.adapters.torch_native import load_scores

        expected = {k: v for k, v in candidate.architecture.config.items() if k != "training"}
        payload = torch.load(path, weights_only=True)
        payload["state_dict"].pop(next(iter(payload["state_dict"])))
        broken = tmp_path / "broken.pt"
        torch.save(payload, broken)
        with pytest.raises(RuntimeError, match="Missing key"):
            load_scores(str(broken), "lstm", expected, X)
        payload = torch.load(path, weights_only=True)
        payload["scaler_scale"][0] = 0
        torch.save(payload, broken)
        with pytest.raises(ValueError, match="scaler"):
            load_scores(str(broken), "lstm", expected, X)
        with pytest.raises(ValueError, match="input shape"):
            load_scores(str(path), "lstm", expected, X[:, :-1])
        wrong = {**expected, "torch_version": "0"}
        with pytest.raises(ValueError, match="passport architecture"):
            load_scores(str(path), "lstm", wrong, X)
        for key, value in (
            ("model_type", "tcn"),
            ("architecture_revision", "bad"),
            ("constructor", {"hidden_size": 1}),
            ("class_order", [1, 0]),
            ("threshold", 0.4),
        ):
            payload = torch.load(path, weights_only=True)
            payload[key] = value
            torch.save(payload, broken)
            with pytest.raises(ValueError):
                load_scores(str(broken), "lstm", expected, X)
    finally:
        set_service("tool_invoker", previous)
