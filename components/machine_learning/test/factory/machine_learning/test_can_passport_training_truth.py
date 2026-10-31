"""Artifact-bearing CAN rows fail closed when passport publication fails."""
from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from factory.machine_learning.runtime.can_contract_training import train_can_contracts
from factory.machine_learning.runtime.can_passports import CanPassportContext
from factory.machine_learning.runtime.ports import TimeSeriesModelType

from .can_contract_fixtures import contract, refs, window


def test_publication_failure_is_terminal_unpassported(tmp_path: Path) -> None:
    feature_contract = contract(tmp_path)
    schema_ref, policy_ref = refs(tmp_path)
    windows = tmp_path / "windows.jsonl"
    windows.write_text(json.dumps(window(feature_contract)) + "\n")
    model = tmp_path / "model.joblib"
    model.write_bytes(b"model")
    info = {
        "x_2d_uri": (tmp_path / "x2.npy").as_uri(),
        "x_3d_uri": (tmp_path / "x3.npy").as_uri(),
        "n_samples": 1, "n_features": 2, "window_size": 2,
        "label_dist": {"0": 1},
    }
    runtime = MagicMock()
    with patch(
        "factory.machine_learning.runtime.can_contract_training.convert_records_to_npy",
        return_value=(info["x_2d_uri"], (tmp_path / "y.npy").as_uri(), info),
    ), patch(
        "factory.machine_learning.runtime.can_contract_training._train_one",
        return_value=(
            SimpleNamespace(id="job", model_path=str(model)),
            {"metrics": {"auroc": 0.8}, "model_type": "lightgbm"},
        ),
    ), patch(
        "factory.machine_learning.runtime.can_contract_training.issue_can_model_passport",
        side_effect=ValueError("Dataset MCP verification failed"),
    ):
        table, warm_ids = train_can_contracts(
            trainer=MagicMock(), runtime=runtime, augmented_uri=windows.as_uri(),
            top_n=1, vehicle_id="v", snapshots_dir=tmp_path,
            model_types=[TimeSeriesModelType.lightgbm], source_digests=[],
            signal_schema_refs={"0x1": schema_ref},
            prior_data_policy_ref=policy_ref,
            passport_context=CanPassportContext((), None, str(tmp_path)),
            require_passport=True,
        )
    assert warm_ids == []
    assert table[0]["registration_status"] == "failed"
    assert table[0]["passport_status"] == "unpassported"
    assert table[0]["error_code"] == "passport_publication_failed"
    runtime.register_inference_model.assert_not_called()
