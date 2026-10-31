"""Property coverage for collision-safe CAN frame IDs and Trip bounds."""
from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.dataset.runtime.adapters.can_taxonomize import CanTaxonomizeStageAdapter


class RecordingGraph:
    """Public graph-adapter double that records projected values."""

    def __init__(self) -> None:
        self.entities: dict[str, object] = {}
        self.relationships: list[object] = []

    def add_entity(self, entity):
        self.entities[entity.id] = entity
        return entity

    def add_relationship(self, relationship):
        self.relationships.append(relationship)
        return relationship


def _record(timestamp_ns: int) -> dict:
    return {
        "vehicle_id": "vehicle", "trip_id": "trip", "bus_name": "CAN1",
        "timestamp_ns": timestamp_ns, "arbitration_id": "0x100",
        "is_extended": False, "is_fd": False, "dlc": 8,
        "data_bytes": "0000000000000000", "decoded_signals": {},
    }


@given(timestamps=st.lists(
    st.integers(min_value=0, max_value=2**63 - 1), min_size=1, max_size=12,
))
@settings(max_examples=50, deadline=None)
def test_duplicate_frames_remain_distinct_and_trip_bounds_are_exact(
    timestamps: list[int],
) -> None:
    records = [_record(value) for value in [*timestamps, timestamps[0]]]
    graph = RecordingGraph()

    list(CanTaxonomizeStageAdapter(graph=graph).execute(records, {}))

    frames = [item for item in graph.entities.values() if item.type == "Frame"]
    assert len(frames) == len(records)
    assert len({item.id for item in frames}) == len(records)
    trip = graph.entities["trip-vehicle-trip"]
    assert trip.properties["start_ts"] == min(timestamps)
    assert trip.properties["end_ts"] == max(timestamps)
