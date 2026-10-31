"""Context/provenance preservation invariants for CAN synthesis and augmentation."""
from __future__ import annotations

import numpy as np

from factory.dataset.runtime.adapters.can_augment import CanAugmentStageAdapter
from factory.dataset.runtime.adapters.can_synthesize import CanSynthesizeStageAdapter
from factory.dataset.runtime.adapters.can_synthesize_helpers import build_records


def test_deterministic_donor_context_and_lineage_survive_synthesis() -> None:
    donors = [
        {"timestamp_ns": 20, "trip_id": "b", "arbitration_id": "0x1",
         "capture_source": "real", "context": {"temp": 20.0},
         "source_lineage": [{"digest": "b"}]},
        {"timestamp_ns": 10, "trip_id": "a", "arbitration_id": "0x1",
         "capture_source": "real", "context": {"temp": 10.0},
         "source_lineage": [{"digest": "a"}]},
    ]
    records = build_records(
        template=donors[0], donors=donors, arb_id="0x1", signal_names=["s"],
        values=np.asarray([[1.0], [2.0], [3.0]]), period_ns=10,
        vehicle_id="v",
    )
    assert [record["context"]["temp"] for record in records] == [10.0, 20.0, 10.0]
    assert [record["source_lineage"][0]["digest"] for record in records] == ["a", "b", "a"]
    assert all(record["synthetic_lineage"][-1]["synthetic_row"] == index
               for index, record in enumerate(records))


def test_augmentation_mutates_signal_only() -> None:
    record = {
        "window_data": [[1.0], [2.0]], "label": 0,
        "signal": {"columns": ["s"], "values": [[1.0], [2.0]]},
        "context": {"columns": ["temp"], "values": [[10.0], [11.0]]},
        "provenance": {"source_records": [{"digest": "a"}]},
        "arbitration_id": "0x1", "num_timesteps": 2, "trip_id": "t",
    }
    result = list(CanAugmentStageAdapter().execute([record], {
        "techniques": ["scale"], "scale_range": [2.0, 2.0], "seed": 1,
    }))
    augmented = result[1]
    assert augmented["signal"]["values"] == augmented["window_data"]
    assert augmented["signal"]["values"] != record["signal"]["values"]
    assert augmented["context"] == record["context"]
    assert augmented["provenance"] == record["provenance"]
    assert augmented["label"] == record["label"]


def test_complete_world_generation_accepts_context_and_outcome_controls() -> None:
    result = list(CanSynthesizeStageAdapter().execute([], {
        "context_conditioned_failure": True,
        "context_correlation_heatmap": {"temp_c": {"signal_drift": 0.8}},
        "context_features": ["temp_c", "future_operating_state"],
    }))
    assert result == []
