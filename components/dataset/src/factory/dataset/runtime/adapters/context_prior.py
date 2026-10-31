"""Prior-data provenance for context attached to CAN frames."""
from __future__ import annotations

from typing import Any

from ._context_augment_match import _gap_to_record


def context_provenance(
    frame: dict[str, Any], index: dict[str, Any], strategy: str,
    max_delta_ns: int, fill_strategy: str, payload: dict[str, Any],
) -> dict[str, Any]:
    """Retain source-declared observation/availability for one frame."""
    ts = frame.get("timestamp_ns")
    ordered: list[tuple[int, int, dict[str, Any]]] = index.get("sorted") or []
    if type(ts) is not int or not ordered:
        return _empty()
    selected = _selected_records(ts, ordered, strategy, max_delta_ns)
    has_payload = any(value is not None for value in payload.values())
    if not selected and has_payload:
        selected = [record for _start, _end, record in ordered]
    if fill_strategy in {"mean", "last_known"} and has_payload:
        selected.extend(record for _start, _end, record in ordered)
    unique = {id(record): record for record in selected}.values()
    times = [
        (record.get("observed_at_ns"), record.get("available_at_ns"))
        for record in unique
    ]
    if not times or any(type(observed) is not int or type(available) is not int
                        for observed, available in times):
        return _empty()
    return {
        "version": "2.0", "source_kind": "prior_data",
        "observed_at_ns": max(observed for observed, _ in times),
        "available_at_ns": max(available for _, available in times),
        "merge_strategy": strategy,
    }


def _selected_records(
    ts: int, ordered: list[tuple[int, int, dict[str, Any]]],
    strategy: str, max_delta_ns: int,
) -> list[dict[str, Any]]:
    if strategy == "last_known":
        candidates = [row for row in ordered if row[0] <= ts]
        chosen = candidates[-1] if candidates else ordered[0]
        return [chosen[2]] if _within(ts, chosen[2], max_delta_ns) else []
    if strategy == "nearest":
        ranked = [
            (gap, record) for _start, _end, record in ordered
            if (gap := _gap_to_record(ts, record)) is not None
        ]
        if not ranked:
            return []
        gap, record = min(ranked, key=lambda item: item[0])
        return [record] if gap <= max_delta_ns else []
    lower = [row for row in ordered if row[0] <= ts]
    upper = [row for row in ordered if row[0] > ts]
    chosen = ([lower[-1]] if lower else []) + ([upper[0]] if upper else [])
    if not chosen or any(not _within(ts, row[2], max_delta_ns) for row in chosen):
        return []
    return [row[2] for row in chosen]


def _within(ts: int, record: dict[str, Any], limit: int) -> bool:
    gap = _gap_to_record(ts, record)
    return gap is not None and gap <= limit


def _empty() -> dict[str, Any]:
    return {
        "version": "2.0", "source_kind": "prior_data",
        "observed_at_ns": None, "available_at_ns": None,
        "merge_strategy": "none",
    }


__all__ = ["context_provenance"]
