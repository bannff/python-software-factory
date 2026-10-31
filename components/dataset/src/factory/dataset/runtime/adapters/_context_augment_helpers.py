"""Field map and indexing helpers for the context_augment stage.

Split out of :mod:`context_augment` to keep that module under the 200
LOC factory ceiling. Nothing here is part of the public brick surface;
the API may change without notice.

Two concerns live here:

* The flat ``DEFAULT_CONTEXT_FIELDS`` set + ``_FIELD_PATH`` map that
  projects the nested context record (built by ``context_ingest``)
  onto the flat ``context`` sub-object the rest of the pipeline
  consumes as model features.
* :func:`_index_context_records` — turn a list of canonical context
  records into an ordered (start_ns, end_ns) index plus per-field
  aggregates for the ``mean`` / ``last_known`` fill strategies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

# Canonical flat field set and nested-record traversal paths. The
# flat name is what shows up in the output ``context`` sub-object; the
# path is where it lives inside a canonical environment_context
# record produced by ``context_ingest``.
DEFAULT_CONTEXT_FIELDS: tuple[str, ...] = (
    "temp_c", "humidity_pct", "precipitation_mm",
    "road_type", "aggressiveness_score",
    "odometer_km", "battery_health_pct",
    "lat", "lon",
)
_FIELD_PATH: dict[str, tuple[str, ...]] = {
    "temp_c": ("weather", "temp_c"),
    "humidity_pct": ("weather", "humidity_pct"),
    "precipitation_mm": ("weather", "precipitation_mm"),
    "road_type": ("location", "road_type"),
    "lat": ("location", "lat"),
    "lon": ("location", "lon"),
    "aggressiveness_score": ("driving", "aggressiveness_score"),
    "odometer_km": ("vehicle", "odometer_km"),
    "battery_health_pct": ("vehicle", "battery_health_pct"),
}


def _parse_iso_ns(iso: str) -> int:
    """Parse an ISO-8601 string into a nanosecond Unix timestamp."""
    dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    return int(dt.timestamp() * 1_000_000_000)


def _extract_field(ctx_rec: dict[str, Any], flat_name: str) -> Any:
    """Walk ``_FIELD_PATH`` to pull one field out of a context record."""
    cursor: Any = ctx_rec
    for key in _FIELD_PATH[flat_name]:
        if not isinstance(cursor, dict):
            return None
        cursor = cursor.get(key)
    return cursor


def _flatten(rec: dict[str, Any], fields: list[str]) -> dict[str, Any]:
    """Project a canonical context record onto the flat ``fields`` set."""
    return {f: _extract_field(rec, f) for f in fields}


def _index_context_records(
    context_records: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build an ordered index for fast nearest / interpolation lookups.

    Returns a dict with:

    * ``sorted`` — list of (start_ns, end_ns, ctx_rec) sorted by start.
    * ``field_means`` — per-flat-field mean over all finite values
      (used by ``fill_strategy="mean"``).
    * ``field_last_known`` — per-flat-field chronologically-last
      finite value (used by ``fill_strategy="last_known"``).
    """
    ordered: list[tuple[int, int, dict[str, Any]]] = []
    for rec in context_records:
        start = rec.get("window_start")
        end = rec.get("window_end")
        if not isinstance(start, str) or not isinstance(end, str):
            continue
        try:
            start_ns = _parse_iso_ns(start)
            end_ns = _parse_iso_ns(end)
        except ValueError:
            continue
        ordered.append((start_ns, end_ns, rec))
    ordered.sort(key=lambda row: row[0])

    field_values: dict[str, list[float]] = {f: [] for f in DEFAULT_CONTEXT_FIELDS}
    field_last: dict[str, Any] = {}
    for _, _, rec in ordered:
        for f in DEFAULT_CONTEXT_FIELDS:
            v = _extract_field(rec, f)
            # bool is an int subclass; treat as non-numeric so we
            # don't average booleans into the mean table.
            if isinstance(v, bool):
                field_last[f] = v
                continue
            if isinstance(v, (int, float)):
                field_values[f].append(float(v))
                field_last[f] = v
            elif v is not None:
                field_last[f] = v
    field_means = {f: (sum(vs) / len(vs) if vs else None) for f, vs in field_values.items()}
    return {"sorted": ordered, "field_means": field_means, "field_last_known": field_last}
