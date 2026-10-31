"""Native flavor-tree integrity and exact-passport fresh-process conformance."""
from __future__ import annotations

import asyncio
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from factory.machine_learning.runtime.adapters.mlflow_lightgbm import (
    load_lightgbm_flavor, validated_probabilities,
)
from factory.machine_learning.runtime.passport_composition import (
    create_local_passport_service,
)
from factory.machine_learning.runtime.passport_inference import (
    ModelNotPromotableError, _require_promoted_lightgbm,
)
from factory.machine_learning.runtime.passport_snapshot import verified_snapshot
from factory.machine_learning.runtime.passport_store_models import ModelPassportRef
from factory.machine_learning.runtime.passport_trees import (
    flavor_tree_manifest, mlflow_lightgbm_artifact_ref,
)
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service

from .lightgbm_passport_subprocess_support import (
    FRESH_SCORE_SCRIPT, candidate, fresh_predict,
)


def test_tree_manifest_is_sorted_complete_and_rejects_symlinks(tmp_path: Path) -> None:
    model = tmp_path / "model"
    (model / "z").mkdir(parents=True)
    (model / "b.txt").write_bytes(b"bb")
    (model / "z" / "a.txt").write_bytes(b"a")
    manifest = flavor_tree_manifest(model, tmp_path)
    assert [entry["path"] for entry in manifest["entries"]] == ["b.txt", "z", "z/a.txt"]
    assert manifest["total_size_bytes"] == 3
    files = [entry for entry in manifest["entries"] if entry["type"] == "file"]
    assert all(len(entry["sha256"]) == 64 and entry["size_bytes"] > 0 for entry in files)
    assert mlflow_lightgbm_artifact_ref("model", model, tmp_path).size_bytes == 3
    with pytest.raises(ValueError, match="escapes"):
        flavor_tree_manifest(tmp_path.parent, tmp_path)
    (model / "link").symlink_to(model / "b.txt")
    with pytest.raises(ValueError, match="symlinks"):
        flavor_tree_manifest(model, tmp_path)


def test_candidate_promotes_then_cold_predicts_and_tamper_fails_before_scoring(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    passport_root, dataset_root = tmp_path / "passports", tmp_path / "datasets"
    passport_root.mkdir()
    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", str(passport_root))
    monkeypatch.setenv("ML_ENABLE_AUTHORING_TOOLS", "1")
    previous = get_service("tool_invoker")
    try:
        (
            value, publication, feature_contract, training, synthesis,
            job, validation_path,
        ) = candidate(passport_root, dataset_root)
        assert value.promotion_status == "candidate"
        assert value.inference.loader == "mlflow.lightgbm"
        assert value.model_artifact.format == "mlflow-lightgbm"
        tool = asyncio.run(create_mcp_server().get_tool(
            "ml_verify_and_promote_lightgbm_passport"
        ))
        source = publication.ref.model_dump(mode="json")
        promoted = tool.fn(
            model_id=source["model_id"], model_version=source["model_version"],
            passport_revision=source["passport_revision"], passport_uri=source["uri"],
            passport_digest=source["digest"],
        )
        assert promoted.ok and promoted.data is not None
        assert promoted.data.status == "published", promoted
        assert promoted.data.ref.passport_revision == 2
        promoted_ref = promoted.data.ref
        verified = create_local_passport_service(passport_root).get(promoted_ref)
        assert verified.promotion_status == "promotable"
        assert verified.conformance_status == "passed"
        assert verified.predecessor and verified.predecessor.digest == publication.ref.digest
        assert verified.model_artifact == value.model_artifact
        assert verified.preparation == value.preparation
        rejected = (
            verified.model_copy(update={"passport_revision": 1}),
            verified.model_copy(update={
                "architecture": verified.architecture.model_copy(
                    update={"framework": "torch"},
                ),
            }),
            verified.model_copy(update={
                "inference": verified.inference.model_copy(
                    update={"loader": "torch.state_dict"},
                ),
            }),
        )
        for altered in rejected:
            with pytest.raises(ModelNotPromotableError):
                _require_promoted_lightgbm(altered)
        validation_X = np.load(validation_path, allow_pickle=False)
        warm = np.asarray(job.val_y_score)
        assert warm.ndim == 1 and len(warm) == len(validation_X)
        with verified_snapshot(verified, passport_root, ("model",)) as snapshot:
            with pytest.raises(ValueError, match="feature width"):
                load_lightgbm_flavor(
                    snapshot["model"],
                    expected_width=verified.preparation.contract_width + 1,
                )
            cold = validated_probabilities(
                load_lightgbm_flavor(snapshot["model"]), validation_X,
            )[:, 1]
        np.testing.assert_allclose(warm, cold, rtol=0, atol=0)
        completed = subprocess.run(
            [sys.executable, "-c", FRESH_SCORE_SCRIPT], check=True,
            input=json.dumps({
                "root": str(passport_root), "dataset_root": str(dataset_root),
                "ref": promoted_ref.model_dump(mode="json"), "x": str(validation_path),
                "lineage": {
                    training["dataset_uri"]: training,
                    synthesis["dataset_uri"]: synthesis,
                },
            }), text=True, capture_output=True,
        )
        fresh = np.asarray(json.loads(completed.stdout))
        np.testing.assert_allclose(cold, fresh, rtol=0, atol=0)
        marker = passport_root / "scored.marker"
        result = fresh_predict(
            passport_root, dataset_root, promoted_ref.model_dump(mode="json"), feature_contract,
            training, synthesis, marker,
        )
        assert result["ok"] and result["data"]["status"] == "ok"
        assert marker.read_text() == "scored"
        marker.unlink()
        model_file = Path(value.model_artifact.uri.removeprefix("file://")) / "MLmodel"
        model_file.write_text(model_file.read_text() + "\n# tampered")
        denied = fresh_predict(
            passport_root, dataset_root, promoted_ref.model_dump(mode="json"), feature_contract,
            training, synthesis, marker,
        )
        assert not denied["ok"] and denied["data"] is None
        assert "failed retrieval or verification" in denied["error"]
        assert not marker.exists()
    finally:
        set_service("tool_invoker", previous)
