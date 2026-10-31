"""Dataset-owned temporal windowing for CAN model inputs and labels."""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Iterator
from typing import Any

from .can_window_builder import (
    _timestamp, build_window, compute_timespans, validate_timing_order,
)
from ..can_window_contracts import CanContextFeaturePolicy

_FORBIDDEN_FEATURES = frozenset({
    "label", "target", "is_failure", "failure_mode", "failure_strategy",
    "failure_timestamp_ns", "correlation", "correlation_heatmap",
    "provenance", "source_lineage", "synthetic_lineage", "timestamp_ns",
})


class CanWindowStageAdapter:
    """Emit v2 signal/context/provenance planes with split X/y intervals."""

    name = "can_window"
    stage_version = "factory-can-window-2"
    allowed_config = frozenset({
        "window_size_ms", "step_size_ms", "grid_resolution_ms", "input_uri",
        "emit_timespans", "signal_columns", "signal_columns_by_can_id",
        "context_columns", "context_feature_policy",
        "observation_cutoff_ms", "label_horizon_ms",
    })

    def execute(
        self, records: Iterable[Any], config: dict[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(f"Unsupported can_window configuration: {sorted(unknown)}")
        window_ms = _positive(values, "window_size_ms", 5000)
        step_ms = _positive(values, "step_size_ms", window_ms)
        grid_ms = _positive(values, "grid_resolution_ms", 10)
        cutoff_ms = _positive(values, "observation_cutoff_ms", window_ms)
        horizon_ms = int(values.get("label_horizon_ms", 0))
        if horizon_ms < 0:
            raise ValueError("label_horizon_ms must be >= 0")
        if cutoff_ms % grid_ms:
            raise ValueError("observation_cutoff_ms must be divisible by grid_resolution_ms")
        signal_map = values.get("signal_columns_by_can_id")
        if signal_map is not None and not isinstance(signal_map, dict):
            raise ValueError("signal_columns_by_can_id must be an object")
        if signal_map is not None and values.get("signal_columns") is not None:
            raise ValueError("configure signal_columns or signal_columns_by_can_id, not both")
        policy = CanContextFeaturePolicy.model_validate(
            values.get("context_feature_policy") or {},
        )

        record_list = list(records)
        if not record_list and values.get("input_uri"):
            input_uri = str(values["input_uri"])
            from .can_input_guard import guard_standalone_can_input
            guard_standalone_can_input(input_uri)
            record_list = _load_records_from_uri(input_uri)
        by_can: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for record in record_list:
            if record.get("decoded_signals"):
                by_can[str(record["arbitration_id"])].append(record)
        emit_timespans = bool(values.get("emit_timespans", False))
        for can_id, group in sorted(by_can.items()):
            if emit_timespans:
                validate_timing_order(group)
            group.sort(key=_timestamp)
            configured_signal = (
                signal_map.get(can_id) if signal_map is not None
                else values.get("signal_columns")
            )
            if signal_map is not None and configured_signal is None:
                raise ValueError(f"signal columns missing for CAN-ID {can_id}")
            signal_columns = _columns(configured_signal, group, "decoded_signals")
            context_columns = _columns(values.get("context_columns", []), group, "context")
            _validate_columns(signal_columns, "signal")
            _validate_columns(context_columns, "context")
            _validate_context_policy(context_columns, policy)
            if not signal_columns:
                continue
            yield from _windows(
                group, can_id=can_id, signal_columns=signal_columns,
                context_columns=context_columns, context_policy=policy,
                window_ms=window_ms,
                step_ms=step_ms, grid_ms=grid_ms, cutoff_ms=cutoff_ms,
                horizon_ms=horizon_ms,
                emit_timespans=emit_timespans,
            )


def _windows(
    group: list[dict[str, Any]], *, can_id: str, signal_columns: list[str],
    context_columns: list[str], context_policy: CanContextFeaturePolicy,
    window_ms: int, step_ms: int, grid_ms: int,
    cutoff_ms: int, horizon_ms: int, emit_timespans: bool,
    exact_v2: bool = False, metadata: dict[str, Any] | None = None,
) -> Iterator[dict[str, Any]]:
    step_ns, grid_ns = step_ms * 1_000_000, grid_ms * 1_000_000
    cutoff_delta, horizon_delta = cutoff_ms * 1_000_000, horizon_ms * 1_000_000
    start, final_ts = _timestamp(group[0]), _timestamp(group[-1])
    required_end_delta = cutoff_delta + horizon_delta
    while start + required_end_delta <= final_ts + grid_ns:
        cutoff, label_end = start + cutoff_delta, start + required_end_delta
        window = build_window(
            group, can_id=can_id, start_ns=start,
            observation_cutoff_ns=cutoff, label_end_ns=label_end,
            grid_ns=grid_ns, signal_columns=signal_columns,
            context_columns=context_columns, context_policy=context_policy,
            window_size_ms=window_ms,
            step_size_ms=step_ms, grid_resolution_ms=grid_ms,
            observation_cutoff_ms=cutoff_ms, label_horizon_ms=horizon_ms,
            metadata=metadata,
        )
        if window is not None:
            payload = window.model_dump(mode="json") if exact_v2 else window.serialized()
            if emit_timespans:
                payload["timespans"] = compute_timespans(group, start, cutoff, grid_ns)
            yield payload
        start += step_ns


def _columns(
    configured: Any, records: list[dict[str, Any]], field: str,
) -> list[str]:
    if configured is not None:
        columns = [str(item) for item in configured]
        available = {str(key) for record in records for key in (record.get(field) or {})}
        missing = [column for column in columns if column not in available]
        if missing:
            raise ValueError(f"{field} columns missing from records: {missing}")
        return columns
    return sorted({str(key) for record in records for key in (record.get(field) or {})})


def _validate_columns(columns: list[str], plane: str) -> None:
    if len(columns) != len(set(columns)):
        raise ValueError(f"duplicate {plane} columns are not allowed")
    forbidden = [name for name in columns if name.lower() in _FORBIDDEN_FEATURES]
    if forbidden:
        raise ValueError(f"forbidden {plane} columns: {forbidden}")


def _validate_context_policy(
    columns: list[str], policy: CanContextFeaturePolicy,
) -> None:
    if bool(columns) != policy.use_context:
        raise ValueError("context columns and context feature policy disagree")
    if set(columns) != set(policy.prior_data_allowlist):
        raise ValueError("context columns must exactly match the prior-data allowlist")


def _positive(values: dict[str, Any], name: str, default: int) -> int:
    value = int(values.get(name, default))
    if value <= 0:
        raise ValueError(f"{name} must be > 0")
    return value


def _load_records_from_uri(uri: str) -> list[dict[str, Any]]:
    from ..helpers import load_records_from_uri
    return load_records_from_uri(uri)


__all__ = ["CanWindowStageAdapter"]
