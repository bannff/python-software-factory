"""Native LTC passport lifecycle parity and pre-execution denial acceptance."""
from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

torch = pytest.importorskip("torch", reason="LNN tests require the ml group")
ncps_torch = pytest.importorskip("ncps.torch", reason="LNN tests require the ml group")
LTC = ncps_torch.LTC

from factory.machine_learning.runtime.adapters.lnn_native import (
    load_scores, passport_config, timing_artifact,
)
from factory.machine_learning.runtime.model_passport import ModelPassport
from factory.machine_learning.runtime.passport_codec import create_model_passport
from factory.machine_learning.runtime.live_timing import LiveTimingArtifactRef
from factory.machine_learning.runtime.passport_composition import create_local_passport_service
from factory.machine_learning.runtime.passport_native_inference import load_neural_passport_scores
from factory.machine_learning.runtime.passport_probe import run as run_probe
from factory.machine_learning.runtime.passport_probe_contracts import PassportProbeInput
from factory.machine_learning.runtime.passport_snapshot import verified_snapshot

from .lnn_passport_fixtures import lnn_passport_case
from .neural_passport_subprocess_support import FRESH_NEURAL_SCORE_SCRIPT


def _payload(case: dict, passport: ModelPassport, snapshot: dict[str, Path]) -> PassportProbeInput:
    return PassportProbeInput(
        passport=passport, snapshot_root=str(snapshot["root"]),
        model_path=str(snapshot["model"]),
        contract_path=str(snapshot["feature_contract"]),
        prepared_x_path=str(snapshot["prepared_x"]),
        prepared_y_path=str(snapshot["prepared_y"]),
        prepared_timespans_path=str(snapshot["prepared_timespans"]), nonce="qa-lnn",
    )


def _alter(passport: ModelPassport, **updates) -> ModelPassport:
    body = passport.model_dump(mode="python", exclude={"passport_digest"})
    body.update(updates)
    return create_model_passport(**body)


def test_lnn_candidate_promotion_cold_and_fresh_process_parity(lnn_passport_case) -> None:
    case = lnn_passport_case
    candidate, X = case["candidate"], case["X"]
    config = passport_config(case["job"].model_path)
    timing, scale, digest = timing_artifact(str(case["timing_path"]), (20, 10))
    validation_scores = load_scores(
        case["job"].model_path, config,
        case["validation_X"], case["validation_timing"],
    )
    np.testing.assert_array_equal(
        np.asarray(case["job"].val_y_pred), validation_scores.argmax(axis=1),
    )
    np.testing.assert_allclose(
        np.asarray(case["job"].val_y_score), validation_scores[:, 1],
        rtol=0, atol=1e-7,
    )
    warm_scores = load_scores(case["job"].model_path, config, X, timing)
    np.testing.assert_array_equal(case["warm"]["y_pred"], warm_scores.argmax(axis=1))
    np.testing.assert_allclose(
        case["warm"]["y_score"], warm_scores[:, 1], rtol=0, atol=1e-7,
    )
    assert candidate.inference.loader == "ncps.torch.LTC.state_dict"
    assert candidate.architecture.framework == "ncps"
    assert candidate.architecture.framework_version == "1.0.1"
    assert Path(case["job"].model_path).resolve().is_relative_to(case["root"].resolve())
    assert candidate.preparation.timespans.digest == digest
    assert timing.dtype == np.float64
    assert scale == case["timing"].mean(dtype=np.float64)
    assert config["timing_scale"] == scale and config["timing_shape"] == [20, 10]
    assert config["scaler_dtype"] == "torch.float64"
    assert config["timing_dtype"] == "float64" and config["ncps_version"] == "1.0.1"
    roles = ("model", "feature_contract", "prepared_x", "prepared_y", "prepared_timespans")
    with verified_snapshot(candidate, case["root"], roles) as snapshot:
        probe = run_probe(_payload(case, candidate, snapshot))
    assert probe.probe_output_digest == hashlib.sha256(warm_scores.tobytes()).hexdigest()
    assert probe.predictions_digest == hashlib.sha256(warm_scores.argmax(axis=1).tobytes()).hexdigest()
    service = create_local_passport_service(case["root"])
    promoted_ref = service.verify_and_promote(case["publication"].ref).ref
    promoted = service.get(promoted_ref)
    assert promoted.passport_revision == 2
    assert {item.verifier_identity for item in promoted.conformance_evidence} == {
        "local-ncps-ltc-isolated-v1",
    }
    live_x = X[:7]
    live_timing = timing[:7] * 1.25
    live_x_path = case["root"] / "live-X.npy"
    live_timing_path = case["root"] / "live-timing.npy"
    np.save(live_x_path, live_x)
    np.save(live_timing_path, live_timing)
    live_ref = LiveTimingArtifactRef(
        uri=live_timing_path.as_uri(),
        digest=hashlib.sha256(live_timing_path.read_bytes()).hexdigest(),
    )
    expected = load_scores(case["job"].model_path, config, live_x, live_timing)
    cold = load_neural_passport_scores(service, promoted_ref, live_x, live_ref)
    np.testing.assert_array_equal(cold.argmax(axis=1), expected.argmax(axis=1))
    np.testing.assert_allclose(cold[:, 1], expected[:, 1], rtol=0, atol=1e-7)
    completed = subprocess.run(
        [sys.executable, "-c", FRESH_NEURAL_SCORE_SCRIPT], check=True,
        input=json.dumps({"root": str(case["root"]),
                          "ref": promoted_ref.model_dump(mode="json"),
                          "x": str(live_x_path),
                          "live_timing": live_ref.model_dump(mode="json")}),
        text=True, capture_output=True,
    )
    fresh = np.asarray(json.loads(completed.stdout))
    np.testing.assert_array_equal(fresh.argmax(axis=1), cold.argmax(axis=1))
    np.testing.assert_allclose(fresh[:, 1], cold[:, 1], rtol=0, atol=1e-7)


def test_all_lnn_tamper_classes_fail_before_ltc_execution(
    lnn_passport_case, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    case, candidate = lnn_passport_case, lnn_passport_case["candidate"]
    X, timing = case["X"], case["timing"]
    path, config = Path(case["job"].model_path), passport_config(case["job"].model_path)

    def forbidden(*args, **kwargs):
        raise AssertionError("LTC.forward executed for denied input")

    monkeypatch.setattr(LTC, "forward", forbidden)
    invalid_timing = (
        np.full((20, 10), "x", dtype=object), np.full((20, 10), np.nan),
        np.full((20, 10), np.inf), np.zeros((20, 10)),
        -np.ones((20, 10)), np.ones((20, 9)),
    )
    for values in invalid_timing:
        with pytest.raises(ValueError, match="timespans"):
            load_scores(path, config, X, values)
    with pytest.raises(FileNotFoundError):
        timing_artifact(str(tmp_path / "missing.npy"), (20, 10))

    base = torch.load(path, weights_only=True)
    for defect in ("weights", "config", "scaler", "framework"):
        payload = copy.deepcopy(base)
        if defect == "weights":
            payload["state_dict"].pop(next(iter(payload["state_dict"])))
        elif defect == "config":
            payload["constructor"] = {"hidden_size": 1}
        elif defect == "scaler":
            payload["scaler_scale"][0] = 0
        else:
            payload["ncps_version"] = "0"
        broken = tmp_path / f"{defect}.pt"
        torch.save(payload, broken)
        with pytest.raises((ValueError, RuntimeError)):
            load_scores(broken, config, X, timing)

    roles = ("model", "feature_contract", "prepared_x", "prepared_y", "prepared_timespans")
    with verified_snapshot(candidate, case["root"], roles) as snapshot:
        original = _payload(case, candidate, snapshot)
        timing_ref = candidate.preparation.timespans
        bad_digest = timing_ref.model_copy(update={"digest": "0" * 64})
        altered = (
            _alter(candidate, preparation=candidate.preparation.model_copy(
                update={"timespans": bad_digest})),
            _alter(candidate, preparation=candidate.preparation.model_copy(
                update={"timespans_shape": (20, 9)})),
            _alter(candidate, preparation=candidate.preparation.model_copy(
                update={"x_shape": (20, 9, 2)})),
            _alter(candidate, architecture=candidate.architecture.model_copy(
                update={"config": {**candidate.architecture.config,
                                   "timing_scale": config["timing_scale"] * 2}})),
            _alter(candidate, architecture=candidate.architecture.model_copy(
                update={"framework": "torch"})),
            _alter(candidate, inference=candidate.inference.model_copy(
                update={"loader": "torch.state_dict"})),
            candidate.model_copy(update={"passport_revision": 2}),
        )
        with pytest.raises(ValueError, match="timing snapshot"):
            run_probe(original.model_copy(update={"prepared_timespans_path": None}))
        for passport in altered:
            with pytest.raises(ValueError):
                run_probe(original.model_copy(update={"passport": passport}))

    service = create_local_passport_service(case["root"])
    for artifact in (path, case["timing_path"]):
        raw = artifact.read_bytes()
        artifact.write_bytes(raw + b"tamper")
        with pytest.raises(ValueError, match="exact bytes|snapshot"):
            service.verify_and_promote(case["publication"].ref)
        artifact.write_bytes(raw)
