"""Acceptance tests for causal CAN timing-plane preservation."""
from __future__ import annotations

import pytest

from factory.dataset.runtime.adapters.can_augment import CanAugmentStageAdapter


def _timed_window() -> dict:
    return {
        "signal": {"columns": ["a"], "values": [[1.0], [2.0], [3.0]]},
        "window_data": [[1.0], [2.0], [3.0]],
        "timespans": [10.0, 20.0, 30.0],
        "label": 0, "trip_id": "timed", "capture_source": "source",
    }


def test_value_only_augmentation_preserves_exact_timing_plane() -> None:
    result = list(CanAugmentStageAdapter().execute(
        [_timed_window()], {"techniques": ["jitter", "scale"], "seed": 9},
    ))
    assert len(result) == 3
    assert all(item["timespans"] == [10.0, 20.0, 30.0] for item in result)


@pytest.mark.parametrize("technique", ["warp", "permute"])
def test_time_axis_augmentation_with_exact_timing_fails_closed(technique: str) -> None:
    with pytest.raises(ValueError, match="incompatible with exact timespans"):
        list(CanAugmentStageAdapter().execute(
            [_timed_window()], {"techniques": [technique]},
        ))
