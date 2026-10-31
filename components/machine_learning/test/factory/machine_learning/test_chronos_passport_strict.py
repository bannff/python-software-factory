"""Fail-closed Chronos passport, probe, scaler, and framework contracts."""
from pathlib import Path

import pytest

torch = pytest.importorskip("torch", reason="Chronos tests require the ml group")
pytest.importorskip("chronos", reason="Chronos tests require the ml group")
pytest.importorskip("peft", reason="Chronos tests require the ml group")

from factory.machine_learning.runtime.adapters.chronos_native import passport_config
from factory.machine_learning.runtime.passport_tree_seal import seal_read_only_tree
from factory.machine_learning.runtime.passport_trees import chronos_native_artifact_ref
from factory.machine_learning.runtime.passport_native_inference import (
    _load_neural_snapshot_scores, load_neural_passport_scores,
)
from factory.machine_learning.runtime.ports import TimeSeriesModelType
from factory.mcp_utils.interface import get_service, set_service

from .chronos_training_evidence import assert_trained_state_changed
from .test_neural_passport_subprocess import _candidate


def test_chronos_passport_identity_and_scaler_mismatches_fail(tmp_path: Path) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, X, _ = _candidate(tmp_path, TimeSeriesModelType.chronos)
        root = Path(candidate.model_artifact.uri.removeprefix("file://"))
        assert_trained_state_changed(tmp_path / "passports", root, lora=False)
        sealed = candidate.architecture.config
        mutations = (
            {**sealed, "pipeline_class": "wrong.Pipeline"},
            {**sealed, "probe_constructor": {**sealed["probe_constructor"], "dropout": 0.2}},
            {**sealed, "model_class": "wrong.Model"},
            {**sealed, "model_revision": "0" * 40},
            {**sealed, "chronos_version": "0"},
            {**sealed, "peft_version": "0"},
            {**sealed, "scaler_scale": [0.0] * sealed["scaler_length"]},
            {**sealed, "adapter_mode": "lora"},
            {**sealed, "limitations": ["forecasting"]},
        )
        for config in mutations:
            architecture = candidate.architecture.model_copy(update={"config": config})
            altered = candidate.model_copy(update={"architecture": architecture})
            with pytest.raises(ValueError):
                _load_neural_snapshot_scores(altered, root, X)
    finally:
        set_service("tool_invoker", previous)


def test_chronos_probe_rejects_nonpositive_scaler(tmp_path: Path) -> None:
    previous = get_service("tool_invoker")
    try:
        _, candidate, _, _, _ = _candidate(tmp_path, TimeSeriesModelType.chronos)
        root = Path(candidate.model_artifact.uri.removeprefix("file://"))
        probe = root / "probe" / "probe.pt"
        payload = torch.load(probe, weights_only=True)
        payload["scaler_scale"][0] = 0
        probe.chmod(0o600)
        torch.save(payload, probe)
        seal_read_only_tree(root)
        with pytest.raises(ValueError, match="scaler"):
            passport_config(root)
    finally:
        set_service("tool_invoker", previous)


def test_chronos_lora_promotes_fresh_loads_and_rejects_adapter_tamper(
    tmp_path: Path,
) -> None:
    import json
    import subprocess
    import sys

    import numpy as np

    from factory.machine_learning.runtime.passport_composition import (
        create_local_passport_service,
    )
    from factory.machine_learning.runtime.passport_native_inference import (
        load_neural_passport_scores,
    )

    from .neural_passport_subprocess_support import (
        FRESH_NEURAL_SCORE_SCRIPT,
        assert_parity,
    )

    previous = get_service("tool_invoker")
    try:
        root, candidate, publication, X, warm = _candidate(
            tmp_path, TimeSeriesModelType.chronos, lora=True,
        )
        artifact = Path(candidate.model_artifact.uri.removeprefix("file://"))
        assert_trained_state_changed(root, artifact, lora=True)
        assert candidate.architecture.config["adapter_mode"] == "lora"
        assert {item.name for item in (artifact / "adapter").iterdir()} == {
            "README.md", "adapter_config.json", "adapter_model.safetensors",
        }
        service = create_local_passport_service(root)
        promoted_ref = service.verify_and_promote(publication.ref).ref
        tolerance = candidate.architecture.config["parity_tolerance"]
        cold = load_neural_passport_scores(service, promoted_ref, X)[:, 1]
        assert_parity(warm, cold, tolerance)
        completed = subprocess.run(
            [sys.executable, "-c", FRESH_NEURAL_SCORE_SCRIPT], check=True,
            input=json.dumps({
                "root": str(root), "ref": promoted_ref.model_dump(mode="json"),
                "x": str(root / "scoring-X.npy"),
            }),
            text=True, capture_output=True,
        )
        fresh = np.asarray(json.loads(completed.stdout))[:, 1]
        assert_parity(cold, fresh, tolerance)
        adapter_weights = artifact / "adapter" / "adapter_model.safetensors"
        adapter_weights.chmod(0o600)
        adapter_weights.write_bytes(adapter_weights.read_bytes() + b"tamper")
        with pytest.raises(
            ValueError, match="exact bytes|exact model tree|sealed read-only",
        ):
            load_neural_passport_scores(service, promoted_ref, X)
    finally:
        set_service("tool_invoker", previous)


def test_promoted_chronos_write_bit_tamper_fails_all_authorities(
    tmp_path: Path,
) -> None:
    from factory.machine_learning.runtime.passport_composition import (
        create_local_passport_service,
    )

    previous = get_service("tool_invoker")
    try:
        root, candidate, publication, X, _ = _candidate(
            tmp_path, TimeSeriesModelType.chronos,
        )
        service = create_local_passport_service(root)
        promoted_ref = service.verify_and_promote(publication.ref).ref
        artifact = Path(candidate.model_artifact.uri.removeprefix("file://"))
        targets = (artifact, artifact / "backbone", artifact / "probe" / "probe.pt")
        for target in targets:
            target.chmod(target.stat().st_mode | 0o200)
            assert chronos_native_artifact_ref(
                "model", artifact, artifact.parent,
            ).digest == candidate.model_artifact.digest
            with pytest.raises(ValueError, match="sealed read-only"):
                service.get(promoted_ref)
            with pytest.raises(ValueError, match="sealed read-only"):
                load_neural_passport_scores(service, promoted_ref, X)
            with pytest.raises(ValueError, match="sealed read-only"):
                passport_config(artifact)
            seal_read_only_tree(artifact)
            assert service.get(promoted_ref).model_artifact == candidate.model_artifact
    finally:
        set_service("tool_invoker", previous)
