"""Pure builder for Dataset-owned leakage-safe CAN windows."""
from __future__ import annotations

import json
from typing import Any

from ..can_artifact_models import CanContextObservationProvenance
from ..can_window_contracts import (
    CanContextFeaturePolicy, CanFeaturePlane, CanProvenancePlane,
    CanWindowBounds, CanWindowRecord,
)


def build_window(
    records: list[dict[str, Any]], *, can_id: str, start_ns: int,
    observation_cutoff_ns: int, label_end_ns: int, grid_ns: int,
    signal_columns: list[str], context_columns: list[str],
    context_policy: CanContextFeaturePolicy | None, window_size_ms: int,
    step_size_ms: int, grid_resolution_ms: int, observation_cutoff_ms: int,
    label_horizon_ms: int, metadata: dict[str, Any] | None = None,
) -> CanWindowRecord | None:
    """Build one window; X uses only records before the observation cutoff."""
    observation = [r for r in records if start_ns <= _timestamp(r) < observation_cutoff_ns]
    if not observation:
        return None
    _validate_prior_context(observation, context_columns)
    label_records = [
        record for record in records
        if _is_horizon_failure(record, observation_cutoff_ns, label_end_ns)
    ]
    n_grid = observation_cutoff_ms // grid_resolution_ms
    signal_values = normalize_grid(
        _rasterize(observation, signal_columns, start_ns, grid_ns, "decoded_signals"),
        n_grid, len(signal_columns),
    )
    if not any(any(value is not None for value in row) for row in signal_values):
        return None
    context_values = normalize_grid(
        _rasterize(observation, context_columns, start_ns, grid_ns, "context"),
        n_grid, len(context_columns),
    )
    source, synthetic, context_observations = _lineage(observation)
    return CanWindowRecord(
        can_id=can_id,
        vehicle_id=str(observation[0].get("vehicle_id", "unknown")),
        signal=CanFeaturePlane(columns=tuple(signal_columns), values=tuple(map(tuple, signal_values))),
        context=CanFeaturePlane(columns=tuple(context_columns), values=tuple(map(tuple, context_values))),
        provenance=CanProvenancePlane(
            source_records=tuple(source), synthetic_lineage=tuple(synthetic),
            context_observations=tuple(context_observations),
        ),
        bounds=CanWindowBounds(
            window_start_ns=start_ns, observation_cutoff_ns=observation_cutoff_ns,
            label_horizon_end_ns=label_end_ns,
        ),
        label=int(any(bool(r.get("is_failure")) for r in label_records)),
        window_size_ms=window_size_ms, step_size_ms=step_size_ms,
        grid_resolution_ms=grid_resolution_ms,
        observation_cutoff_ms=observation_cutoff_ms,
        label_horizon_ms=label_horizon_ms, num_timesteps=n_grid,
        metadata={
            "label_record_count": len(label_records),
            **(metadata or {
                "context_feature_policy": (
                    context_policy.model_dump(mode="json") if context_policy else None
                ),
            }),
        },
    )


def _validate_prior_context(
    records: list[dict[str, Any]], columns: list[str],
) -> None:
    if not columns:
        return
    for record in records:
        context = record.get("context") or {}
        if not any(context.get(column) is not None for column in columns):
            continue
        provenance = record.get("context_provenance")
        if not isinstance(provenance, dict):
            raise ValueError("context feature is missing observation provenance")
        required = {"observed_at_ns", "available_at_ns"}
        if not required.issubset(provenance):
            raise ValueError("context feature is missing observation provenance")
        if provenance.get("version") != "2.0" or provenance.get("source_kind") != "prior_data":
            raise ValueError("context feature provenance is not prior data")
        observed = provenance["observed_at_ns"]
        available = provenance["available_at_ns"]
        if type(observed) is not int or type(available) is not int:
            raise ValueError("context provenance timestamps must be non-bool integers")
        if observed > available:
            raise ValueError("context observation is not prior data")
        try:
            observation = CanContextObservationProvenance.model_validate(provenance)
        except Exception as exc:
            raise ValueError(f"invalid context observation provenance: {exc}") from exc
        if observation.available_at_ns > _timestamp(record):
            raise ValueError("context feature was not available before the frame")


def validate_timing_order(records: list[dict[str, Any]]) -> None:
    """Reject duplicate or regressing source time before timing-plane sorting."""
    previous: int | None = None
    for record in records:
        current = _timestamp(record)
        if previous is not None and current <= previous:
            raise ValueError("timespan emission requires strictly increasing per-CAN timestamps")
        previous = current


def compute_timespans(
    records: list[dict[str, Any]], start_ns: int, cutoff_ns: int, grid_ns: int,
) -> list[float]:
    """Integrate fixed grid cells without reading the label horizon."""
    cells: list[int | None] = [None] * ((cutoff_ns - start_ns) // grid_ns)
    for record in records:
        ts = _timestamp(record)
        if start_ns <= ts < cutoff_ns:
            cells[min((ts - start_ns) // grid_ns, len(cells) - 1)] = ts
    out: list[float] = []
    previous = start_ns
    for index, _ in enumerate(cells, start=1):
        cell_end = start_ns + index * grid_ns
        out.append(float(cell_end - previous))
        previous = cell_end
    return out


def _rasterize(
    records: list[dict[str, Any]], columns: list[str], start_ns: int,
    grid_ns: int, field: str,
) -> list[list[Any]]:
    n_grid = max(1, (_timestamp(records[-1]) - start_ns) // grid_ns + 1)
    # Caller supplies records bounded by cutoff; pad to the declared grid later.
    declared = max(n_grid, 1)
    values: list[list[Any]] = [[None] * len(columns) for _ in range(declared)]
    for record in records:
        cell = min((_timestamp(record) - start_ns) // grid_ns, declared - 1)
        source = record.get(field) or {}
        for index, column in enumerate(columns):
            if column in source:
                values[cell][index] = source[column]
    return values


def normalize_grid(values: list[list[Any]], timesteps: int, width: int) -> list[list[Any]]:
    """Pad observation cells only; this never creates or removes columns."""
    values.extend([[None] * width for _ in range(timesteps - len(values))])
    return values[:timesteps]


def _lineage(records: list[dict[str, Any]]) -> tuple[list[dict], list[dict], list[dict]]:
    source: list[dict] = []
    synthetic: list[dict] = []
    context_observations: list[dict] = []
    seen: set[str] = set()
    for record in records:
        for key, target in (("source_lineage", source), ("synthetic_lineage", synthetic)):
            value = record.get(key)
            if not value:
                continue
            items = value if isinstance(value, list) else [value]
            for item in items:
                normalized = item if isinstance(item, dict) else {"value": item}
                token = json.dumps(normalized, sort_keys=True, default=str)
                if token not in seen:
                    seen.add(token)
                    target.append(normalized)
        context = record.get("context_provenance")
        if isinstance(context, dict):
            normalized = dict(context)
            token = json.dumps(normalized, sort_keys=True, default=str)
            if token not in seen:
                seen.add(token)
                context_observations.append(normalized)
    return source, synthetic, context_observations


def _is_horizon_failure(record: dict[str, Any], cutoff_ns: int, end_ns: int) -> bool:
    if not bool(record.get("is_failure")):
        return False
    raw = record.get("failure_timestamp_ns")
    event_ns = _timestamp(record) if raw is None else _strict_ns(raw, "failure_timestamp_ns")
    return cutoff_ns <= event_ns < end_ns


def _strict_ns(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be a non-bool integer")
    return value


def _timestamp(record: dict[str, Any]) -> int:
    return _strict_ns(record.get("timestamp_ns"), "timestamp_ns")


__all__ = ["build_window", "compute_timespans", "normalize_grid"]
