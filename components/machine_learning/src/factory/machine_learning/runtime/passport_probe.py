"""Isolated deterministic conformance probe for approved native model bytes."""
from __future__ import annotations

import hashlib
import os
import sys
from pathlib import Path

import numpy as np

from .adapters.mlflow_lightgbm import load_lightgbm_flavor, validated_probabilities
from .can_feature_contract import load_can_feature_contract
from .passport_native_inference import _load_neural_snapshot_scores
from .passport_paths import require_contained_directory, require_contained_file
from .passport_probe_contracts import PassportProbeInput, PassportProbeResult
from .passport_validation import canonical_json


def run(payload: PassportProbeInput) -> PassportProbeResult:
    passport = payload.passport
    if (
        passport.passport_revision != 1
        or passport.promotion_status != "candidate"
        or passport.conformance_status != "not_run"
    ):
        raise ValueError("trusted conformance requires an exact candidate")
    root = Path(payload.snapshot_root).absolute()
    loader = passport.inference.loader
    model_path = (
        require_contained_file(Path(payload.model_path), root)
        if loader == "mlx.nn.Module.load_weights"
        else require_contained_directory(Path(payload.model_path), root)
        if loader in {
            "mlflow.lightgbm", "transformers.patchtst", "chronos.Chronos2Pipeline",
        }
        else require_contained_file(Path(payload.model_path), root)
    )
    contract_path = require_contained_file(Path(payload.contract_path), root)
    x_path = require_contained_file(Path(payload.prepared_x_path), root)
    y_path = require_contained_file(Path(payload.prepared_y_path), root)
    timespans_path = (
        require_contained_file(Path(payload.prepared_timespans_path), root)
        if payload.prepared_timespans_path is not None else None
    )
    contract = load_can_feature_contract(contract_path.as_uri())
    if contract.digest != passport.preparation.materializer.config_digest:
        raise ValueError("snapshotted contract disagrees with passport")
    X = np.load(x_path, allow_pickle=False)
    y = np.load(y_path, allow_pickle=False)
    probe = np.asarray(
        X if loader == "ncps.torch.LTC.state_dict" else X[: min(8, len(X))],
    )
    if probe.shape[0] == 0 or len(y) != len(X):
        raise ValueError("prepared arrays cannot provide a deterministic probe")
    if loader == "mlflow.lightgbm":
        if passport.architecture.framework != "lightgbm" or probe.ndim != 2:
            raise ValueError("LightGBM candidate contract is invalid")
        model = load_lightgbm_flavor(
            model_path, expected_width=passport.preparation.contract_width,
        )
        scores_a = validated_probabilities(model, probe)
        scores_b = validated_probabilities(model, probe)
        predictions = np.asarray(model.predict(probe))
    elif loader in {
        "mlx.nn.Module.load_weights", "torch.state_dict", "transformers.patchtst",
        "ncps.torch.LTC.state_dict", "chronos.Chronos2Pipeline",
    }:
        if loader == "ncps.torch.LTC.state_dict" and timespans_path is None:
            raise ValueError("LNN candidate timing snapshot is absent")
        if loader != "ncps.torch.LTC.state_dict" and timespans_path is not None:
            raise ValueError("non-LNN candidate carried an unexpected timing snapshot")
        scores_a = _load_neural_snapshot_scores(
            passport, model_path, probe, timespans_path,
        )
        scores_b = _load_neural_snapshot_scores(
            passport, model_path, probe, timespans_path,
        )
        predictions = scores_a.argmax(axis=1)
    else:
        raise ValueError("candidate loader is not approved")
    if not np.array_equal(scores_a, scores_b):
        raise ValueError("native model probe is not deterministic")
    return PassportProbeResult(
        child_pid=os.getpid(), parent_nonce=payload.nonce,
        passport_digest=passport.passport_digest,
        model_digest=passport.model_artifact.digest,
        probe_rows=len(probe), probe_width=int(np.prod(probe.shape[1:])),
        probe_input_digest=hashlib.sha256(probe.tobytes()).hexdigest(),
        probe_output_digest=hashlib.sha256(scores_a.tobytes()).hexdigest(),
        predictions_digest=hashlib.sha256(predictions.tobytes()).hexdigest(),
        python=sys.version.split()[0],
    )


def main() -> None:
    try:
        raw = sys.stdin.buffer.read(131_073)
        if len(raw) > 131_072:
            raise ValueError("probe input exceeded limit")
        result = run(PassportProbeInput.model_validate_json(raw, strict=True))
        sys.stdout.buffer.write(canonical_json(result.model_dump(mode="json")))
    except Exception:
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
