"""Focused Metrics focus, navigation, and truthfulness tests."""
from __future__ import annotations

import json

import pytest

from factory.metrics.runtime.adapters.memory import (
    InMemoryMetricsComputer,
    InMemoryMetricsStore,
)
from factory.metrics.runtime.provenance_models import MetricFocus
from factory.metrics.runtime.ports import SourceObservation
from factory.metrics.runtime.runtime import MetricsRuntime
from pydantic import TypeAdapter, ValidationError


def _focus(requested: str = "either") -> dict:
    return {
        "subject_kind": "run",
        "run_id": "run-1",
        "navigation": {
            "version": "v1", "surface": "graph", "target_ref": "run-1",
            "label": "Run 1", "graph_selected_ref": "run-1",
            "graph_context": {"query_ref": "run-1", "neighborhood_limit": 20},
        },
        "label": "Run 1",
        "requested_availability": requested,
        "time_range": {
            "start": "2025-01-01T00:00:00Z",
            "end": "2025-01-01T01:00:00Z",
        },
        "aggregation": "summary",
    }


def _runtime() -> MetricsRuntime:
    return MetricsRuntime(InMemoryMetricsStore(), InMemoryMetricsComputer())


def test_discriminated_focus_preserves_navigation_and_returns_no_durable_state() -> None:
    result = _runtime().measure_focus(_focus())

    assert result.ok
    assert result.focus is not None
    assert result.focus.subject_kind == "run"
    assert result.navigation.graph_selected_ref == "run-1"
    assert result.measurement is not None
    assert result.measurement.measurement_state == "no_durable_measurement"


def test_live_focus_is_explicitly_not_persisted() -> None:
    result = _runtime().measure_focus(_focus("live"))

    assert result.ok
    assert result.measurement is not None
    assert result.measurement.measurement_state == "live_not_persisted"
    assert result.measurement.last_updated_at is not None


def test_execution_focus_requires_exactly_one_native_subject() -> None:
    focus = _focus()
    focus.update({"subject_kind": "execution", "agent_id": "agent-1", "graph_id": "graph-1"})
    result = _runtime().measure_focus(focus)

    assert result.ok is False
    assert result.error_code == "invalid_focus"
    assert result.navigation.target_ref == "run-1"


def test_json_focus_is_strict_and_rejects_extra_fields() -> None:
    parsed = TypeAdapter(MetricFocus).validate_json(json.dumps(_focus()))
    assert parsed.subject_kind == "run"
    with pytest.raises(ValidationError):
        TypeAdapter(MetricFocus).validate_json(json.dumps({**_focus(), "unexpected": True}))


def test_unavailable_store_does_not_claim_durable_measurement() -> None:
    class UnavailableStore(InMemoryMetricsStore):
        def health_check(self) -> dict[str, object]:
            return {"ok": False}

    runtime = MetricsRuntime(UnavailableStore(), InMemoryMetricsComputer())
    result = runtime.measure_focus(_focus())

    assert result.measurement is not None
    assert result.measurement.measurement_state == "source_unavailable"


def test_missing_navigation_returns_typed_invalid_focus() -> None:
    result = _runtime().measure_focus({"subject_kind": "run", "run_id": "run-1"})

    assert result.ok is False
    assert result.error_code == "invalid_focus"
    assert result.navigation is None
    assert result.measurement is None


def test_subject_labeled_point_returns_durable_evidence_and_timestamp() -> None:
    runtime = _runtime()
    timestamp = 1735691400.0
    runtime.store.record("latency", 42.0, {"run_id": "run-1"}, timestamp)

    result = runtime.measure_focus(_focus("durable"))

    assert result.ok
    assert result.measurement is not None
    assert result.measurement.measurement_state == "durable_as_of"
    assert result.measurement.evidence_at is not None
    assert result.measurement.evidence_at.timestamp() == timestamp
    assert result.measurement.last_updated_at == result.measurement.evidence_at


def test_point_after_requested_range_does_not_imply_arrival() -> None:
    runtime = _runtime()
    runtime.store.record("latency", 42.0, {"run_id": "run-1"}, 1735696800.0)

    result = runtime.measure_focus(_focus("durable"))

    assert result.measurement is not None
    assert result.measurement.measurement_state == "no_durable_measurement"


def test_explicit_arriving_observation_returns_still_arriving() -> None:
    runtime = _runtime()
    runtime.store.set_source_observation(SourceObservation(
        disposition="available", arriving=True, watermark=1735693200.0,
        completeness=0.5,
    ))

    result = runtime.measure_focus(_focus("durable"))

    assert result.measurement is not None
    assert result.measurement.measurement_state == "still_arriving"
    assert result.measurement.completeness == 0.5
    assert result.measurement.last_updated_at is not None
    assert result.measurement.last_updated_at.timestamp() == 1735693200.0


@pytest.mark.parametrize("disposition, expected", [
    ("deleted", "source_deleted"),
    ("inaccessible", "source_inaccessible"),
    ("unavailable", "source_unavailable"),
])
def test_explicit_source_disposition_is_preserved(
    disposition: str, expected: str,
) -> None:
    runtime = _runtime()
    runtime.store.set_source_observation(SourceObservation(disposition=disposition))

    result = runtime.measure_focus(_focus("durable"))

    assert result.measurement is not None
    assert result.measurement.measurement_state == expected


def test_query_failure_is_source_unavailable() -> None:
    class FailingQueryStore(InMemoryMetricsStore):
        def query(self, *args: object, **kwargs: object) -> list[object]:
            raise RuntimeError("backend read failed")

    runtime = MetricsRuntime(FailingQueryStore(), InMemoryMetricsComputer())
    runtime.store.record("latency", 42.0, {"run_id": "run-1"}, 1735691400.0)
    result = runtime.measure_focus(_focus("durable"))

    assert result.measurement is not None
    assert result.measurement.measurement_state == "source_unavailable"
    assert result.measurement.reason == "metrics source query failed"
