"""Pure helpers for subject-focused Metrics provenance measurement."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pydantic import TypeAdapter, ValidationError

from .ports import SourceObservation
from .provenance_models import MetricFocus, MetricMeasurement, MetricResult, NavigationRef

if TYPE_CHECKING:
    from .runtime import MetricsRuntime

_FOCUS_ADAPTER = TypeAdapter(MetricFocus)


def _parse_focus(raw_focus: dict[str, Any]) -> MetricFocus:
    """Validate Python callers and JSON/MCP datetime strings strictly."""
    try:
        return _FOCUS_ADAPTER.validate_python(raw_focus, strict=True)
    except ValidationError as first_error:
        try:
            return _FOCUS_ADAPTER.validate_json(json.dumps(raw_focus), strict=True)
        except (TypeError, ValueError, ValidationError):
            raise first_error


def _navigation(raw_focus: dict[str, Any]) -> NavigationRef:
    return NavigationRef.model_validate(raw_focus.get("navigation"))


def _unavailable(
    navigation: NavigationRef, reason: str = "metrics source is unavailable",
) -> MetricMeasurement:
    return MetricMeasurement(
        ok=True,
        navigation=navigation,
        measurement=MetricResult(
            measurement_state="source_unavailable",
            source_class="metrics.store",
            reason=reason,
            next_action="retry_measurement",
        ),
    )


def _lifecycle_result(
    navigation: NavigationRef, observation: SourceObservation,
) -> MetricMeasurement:
    state = {
        "unavailable": "source_unavailable",
        "deleted": "source_deleted",
        "inaccessible": "source_inaccessible",
    }[observation.disposition]
    next_action = {
        "unavailable": "retry_measurement",
        "deleted": "select_another_source",
        "inaccessible": "request_source_access",
    }[observation.disposition]
    return MetricMeasurement(
        ok=True,
        navigation=navigation,
        measurement=MetricResult(
            measurement_state=state,  # type: ignore[arg-type]
            source_class="metrics.store",
            reason=observation.reason or f"metrics source is {observation.disposition}",
            next_action=next_action,
        ),
    )


def _subject_labels(focus: MetricFocus) -> dict[str, str]:
    """Map a validated focus to the exact labels it is allowed to query."""
    kind = focus.subject_kind
    if kind == "run":
        return {"run_id": focus.run_id}
    if kind == "execution":
        subject = next(
            (item for item in ("agent_id", "graph_id", "swarm_id")
             if getattr(focus, item) is not None),
        )
        return {"run_id": focus.run_id, subject: getattr(focus, subject)}
    if kind == "eval":
        labels = {"eval_ref": focus.eval_ref}
        if focus.run_id is not None:
            labels["run_id"] = focus.run_id
        return labels
    if kind == "trace":
        labels = {"trace_id": focus.trace_id}
        if focus.span_id is not None:
            labels["span_id"] = focus.span_id
        return labels
    if kind == "session":
        return {"session_id": focus.session_id}
    if kind == "entity":
        return {"entity_ref": focus.entity_ref}
    return {}


def _metric_ids(runtime: "MetricsRuntime") -> list[str]:
    ids = {item["id"] for item in runtime.list_definitions()}
    list_ids = getattr(runtime.store, "list_metric_ids", None)
    if callable(list_ids):
        ids.update(str(item) for item in list_ids())
    else:
        data = getattr(runtime.store, "_data", None)
        if isinstance(data, dict):
            ids.update(str(item) for item in data)
    return sorted(ids)


def _observe_source(
    runtime: "MetricsRuntime", focus: MetricFocus,
) -> SourceObservation:
    observer = getattr(runtime.store, "observe_source", None)
    if not callable(observer):
        raise RuntimeError("metrics store does not expose source observation")
    return observer(
        labels=_subject_labels(focus),
        start=focus.time_range.start.timestamp(),
        end=focus.time_range.end.timestamp(),
    )


def _query_subject(runtime: "MetricsRuntime", focus: MetricFocus) -> list[Any]:
    labels = _subject_labels(focus)
    if not labels:
        return []
    start = focus.time_range.start.timestamp()
    end = focus.time_range.end.timestamp()
    points: list[Any] = []
    for metric_id in _metric_ids(runtime):
        points.extend(runtime.store.query(
            metric_id, start=start, end=end, labels=labels,
        ))
    return sorted(points, key=lambda point: point.timestamp)


def _durable_result(
    runtime: "MetricsRuntime", focus: MetricFocus, observation: SourceObservation,
) -> MetricResult:
    points = _query_subject(runtime, focus)
    if points:
        latest = points[-1]
        timestamp = datetime.fromtimestamp(latest.timestamp, tz=timezone.utc)
        return MetricResult(
            measurement_state="durable_as_of",
            source_class="metrics.store",
            evidence_at=timestamp,
            last_updated_at=timestamp,
            completeness=(
                observation.completeness
                if observation.completeness is not None else 1.0
            ),
            reason="subject-labeled durable measurement matched",
            next_action=None,
        )

    if observation.arriving:
        watermark = (
            datetime.fromtimestamp(observation.watermark, tz=timezone.utc)
            if observation.watermark is not None else None
        )
        return MetricResult(
            measurement_state="still_arriving",
            source_class="metrics.store",
            evidence_at=None,
            last_updated_at=watermark,
            completeness=observation.completeness,
            reason="metrics backend explicitly reports that subject data is arriving",
            next_action="refresh_measurement",
        )
    return MetricResult(
        measurement_state="no_durable_measurement",
        source_class="metrics.store",
        reason="no subject-labeled durable measurement is available",
        next_action="record_subject_measurement",
    )


__all__ = [
    "_durable_result", "_lifecycle_result", "_navigation", "_observe_source",
    "_parse_focus", "_unavailable",
]
