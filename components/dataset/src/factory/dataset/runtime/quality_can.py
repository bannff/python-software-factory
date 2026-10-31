"""Lightweight quality checks for materialized CAN frame records.

Kept in a sibling module so :mod:`factory.dataset.runtime.quality` stays
under the 200 LOC tenet while the conversation and CAN evaluators each
own a single concern.
"""

from __future__ import annotations

import math
from typing import Any

from .contracts import DatasetQualityResults


def _get_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _record_count(records: list[Any]) -> str:
    return f"passed: {len(records)}"


def _can_ids_valid(records: list[Any]) -> str:
    missing = 0
    for record in records:
        arb = _get_attr(record, "arbitration_id")
        if arb is None or arb == "":
            missing += 1
            continue
        if isinstance(arb, str) and not (arb.startswith("0x") or arb.startswith("0X")):
            return f"failed: malformed arbitration_id: {arb!r}"
    if missing:
        return f"failed: {missing} records missing arbitration_id"
    return "passed"


def _can_timestamps_monotonic(records: list[Any]) -> str:
    last_ts = -1
    regressions = 0
    for record in records:
        ts = _get_attr(record, "timestamp_ns")
        if ts is None:
            continue
        ts = int(ts)
        if ts < last_ts:
            regressions += 1
        last_ts = ts
    if regressions:
        return f"warn: {regressions} timestamp regressions"
    return "passed"


def _can_no_nan_inf(records: list[Any]) -> str:
    bad = 0
    for record in records:
        signals = _get_attr(record, "decoded_signals")
        if not signals:
            continue
        for value in signals.values():
            if isinstance(value, float) and not math.isfinite(value):
                bad += 1
    if bad:
        return f"failed: {bad} NaN/Inf values in decoded_signals"
    return "passed"


def _can_signals_plausible(
    records: list[Any], signal_meta: dict[str, dict[str, Any]] | None
) -> str:
    # Without a signal_meta dict, range validation is impossible; skip cleanly.
    if not signal_meta:
        return "passed"
    out_of_range = 0
    for record in records:
        signals = _get_attr(record, "decoded_signals") or {}
        for name, value in signals.items():
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                continue
            meta = signal_meta.get(name)
            if not meta:
                continue
            lo, hi = meta.get("min"), meta.get("max")
            if (lo is not None and value < lo) or (hi is not None and value > hi):
                out_of_range += 1
    if out_of_range:
        return f"failed: {out_of_range} signal values out of plausible range"
    return "passed"


def _can_failure_consistency(records: list[Any]) -> str:
    inconsistent = 0
    for record in records:
        is_failure = _get_attr(record, "is_failure")
        failure_mode = _get_attr(record, "failure_mode")
        is_f = bool(is_failure) if is_failure is not None else False
        has_mode = failure_mode is not None and failure_mode != ""
        if is_f != has_mode:
            inconsistent += 1
    if inconsistent:
        return f"failed: {inconsistent} inconsistent failure labels"
    return "passed"


def evaluate_can_quality(
    records: list[Any],
    signal_meta: dict[str, dict[str, Any]] | None = None,
) -> DatasetQualityResults:
    """Run lightweight quality checks on materialized CAN frame records.

    ``signal_meta`` is an optional ``{signal_name: {min, max, std}}`` dict;
    when provided, range checks are emitted for each decoded signal.
    """
    checks: dict[str, str] = {
        "record_count": _record_count(records),
        "ids_valid": _can_ids_valid(records),
        "timestamps_monotonic": _can_timestamps_monotonic(records),
        "no_nan_inf": _can_no_nan_inf(records),
        "signals_plausible": _can_signals_plausible(records, signal_meta),
        "failure_consistency": _can_failure_consistency(records),
    }
    return DatasetQualityResults(checks=checks)
