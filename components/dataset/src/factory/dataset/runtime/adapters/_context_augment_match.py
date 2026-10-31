"""Matching strategies + fill policy for the context_augment stage.

Split out of :mod:`context_augment` to keep the public adapter and
its field map under the 200 LOC factory ceiling. Nothing here is
part of the public brick surface; the API may change without notice.

Two concerns live here:

* :func:`_match_context` — under the chosen ``merge_strategy``
  (``nearest`` | ``interpolate`` | ``last_known``), pick (and
  optionally interpolate between) the context record(s) that best
  cover a CAN frame's ``timestamp_ns``.
* :func:`_apply_fill` — materialize a fully-populated ``context``
  sub-object for the frame, applying ``fill_strategy`` to any ``None``
  values left over from the merge step (or fabricating a full payload
  when no context matched within ``max_time_delta_s``).
"""
from __future__ import annotations

from typing import Any

from ._context_augment_helpers import _extract_field, _flatten, _parse_iso_ns


def _gap_to_record(ts_ns: int, rec: dict[str, Any]) -> int | None:
    """Absolute gap (ns) from ``ts_ns`` to the closest edge of ``rec``'s window.

    ``0`` means the timestamp falls inside the window. ``None`` means
    the record's window is malformed (missing or unparseable ISO
    timestamps) and should be skipped.
    """
    start_iso = rec.get("window_start")
    end_iso = rec.get("window_end")
    if not isinstance(start_iso, str) or not isinstance(end_iso, str):
        return None
    try:
        start_ns = _parse_iso_ns(start_iso)
        end_ns = _parse_iso_ns(end_iso)
    except ValueError:
        return None
    if start_ns <= ts_ns <= end_ns:
        return 0
    return min(abs(ts_ns - start_ns), abs(ts_ns - end_ns))


def _match_context(
    frame_rec: dict[str, Any],
    ctx_index: dict[str, Any],
    fields: list[str],
    strategy: str,
    max_delta_ns: int,
) -> dict[str, Any] | None:
    """Return a flat ``field → value`` dict for one frame, or ``None``.

    ``None`` means "no context matched within ``max_delta_ns``" — the
    caller fabricates a fully-filled payload via ``_apply_fill``.
    """
    ts_ns = frame_rec.get("timestamp_ns")
    if not isinstance(ts_ns, (int, float)):
        return None
    ts_ns = int(ts_ns)
    ordered: list[tuple[int, int, dict[str, Any]]] = ctx_index["sorted"]
    if not ordered:
        return None

    if strategy == "last_known":
        chosen = None
        for start, _end, rec in ordered:
            if start <= ts_ns:
                chosen = rec
            else:
                break
        if chosen is None:
            chosen = ordered[0][2]
        gap = _gap_to_record(ts_ns, chosen)
        if gap is not None and gap > max_delta_ns:
            return None
        return _flatten(chosen, fields)

    if strategy == "nearest":
        best_rec = None
        best_gap: int | None = None
        for _start, _end, rec in ordered:
            gap = _gap_to_record(ts_ns, rec)
            if gap is None:
                continue
            if best_gap is None or gap < best_gap:
                best_rec = rec
                best_gap = gap
        if best_rec is None or best_gap is None or best_gap > max_delta_ns:
            return None
        return _flatten(best_rec, fields)

    # strategy == "interpolate": find two records bracketing ``ts_ns``.
    lower = None
    upper = None
    for start, _end, rec in ordered:
        if start <= ts_ns:
            lower = rec
        else:
            upper = rec
            break
    if lower is not None and upper is not None:
        gap = max(_gap_to_record(ts_ns, lower) or 0, _gap_to_record(ts_ns, upper) or 0)
        if gap > max_delta_ns:
            return None
        return _interpolate(lower, upper, ts_ns, fields)
    chosen = lower or upper
    if chosen is None:
        return None
    gap = _gap_to_record(ts_ns, chosen)
    if gap is None or gap > max_delta_ns:
        return None
    return _flatten(chosen, fields)


def _interpolate(
    a: dict[str, Any], b: dict[str, Any],
    ts_ns: int, fields: list[str],
) -> dict[str, Any]:
    """Linearly interpolate numeric fields between two context records.

    For each requested field:

    * If both ``a`` and ``b`` carry a finite numeric value, blend by
      ``t = (ts_ns - a.start_ns) / (b.start_ns - a.start_ns)``.
    * If only one side has a value, take it.
    * If neither has a value, yield ``None`` (caller runs fill).
    * Non-numeric fields (e.g. ``road_type``) take the closer record's
      value via the same ``t`` threshold (0.5 cutoff).
    """
    a_start = _parse_iso_ns(a["window_start"])
    b_start = _parse_iso_ns(b["window_start"])
    span = b_start - a_start
    t = 0.5 if span <= 0 else max(0.0, min(1.0, (ts_ns - a_start) / span))
    out: dict[str, Any] = {}
    for f in fields:
        va = _extract_field(a, f)
        vb = _extract_field(b, f)
        a_num = isinstance(va, (int, float)) and not isinstance(va, bool)
        b_num = isinstance(vb, (int, float)) and not isinstance(vb, bool)
        if a_num and b_num:
            out[f] = float(va) + (float(vb) - float(va)) * t
        elif va is not None and vb is not None:
            out[f] = va if t <= 0.5 else vb
        elif va is not None:
            out[f] = va
        elif vb is not None:
            out[f] = vb
        else:
            out[f] = None
    return out


def _apply_fill(
    payload: dict[str, Any] | None,
    fields: list[str],
    fill_strategy: str,
    ctx_index: dict[str, Any],
) -> dict[str, Any]:
    """Materialize a full ``context`` sub-object applying ``fill_strategy``.

    ``payload=None`` (no context matched within the gap ceiling) maps
    to a fully-fabricated payload per ``fill_strategy``: ``null``
    yields all-None, ``mean`` uses field means across the loaded
    context records, ``last_known`` uses the chronologically-latest
    value seen.
    """
    means = ctx_index.get("field_means") or {}
    last = ctx_index.get("field_last_known") or {}
    out: dict[str, Any] = {}
    for f in fields:
        v = None if payload is None else payload.get(f)
        if v is not None:
            out[f] = v
            continue
        if fill_strategy == "mean" and means.get(f) is not None:
            out[f] = means[f]
        elif fill_strategy == "last_known" and f in last:
            out[f] = last[f]
        else:
            out[f] = None
    return out
