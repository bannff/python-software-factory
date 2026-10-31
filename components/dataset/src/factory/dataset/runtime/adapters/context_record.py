"""Canonical context record assembly with retained source availability."""
from __future__ import annotations

from datetime import datetime
from typing import Any

_PROVENANCE_FIELDS = {"observed_at_ns", "available_at_ns"}


def build_context_record(
    *, vehicle_id: str, window_start: str, window_end: str,
    weather: dict[str, Any] | None, gps: dict[str, Any] | None,
    vehicle: dict[str, Any] | None,
) -> dict[str, Any]:
    """Merge source payloads without inventing observation timestamps."""
    start_dt = datetime.fromisoformat(window_start.replace("Z", "+00:00"))
    location = {"lat": None, "lon": None, "road_type": None}
    if gps:
        location.update({
            "lat": _optional_float(gps.get("lat")),
            "lon": _optional_float(gps.get("lon")),
            "road_type": gps.get("road_type"),
        })
    record = {
        "context_id": f"envctx-{vehicle_id}-{int(start_dt.timestamp())}",
        "window_start": window_start, "window_end": window_end,
        "vehicle_id": vehicle_id, "weather": _feature_values(weather),
        "location": location, "driving": {}, "vehicle": _feature_values(vehicle),
    }
    sources = [
        source for source in (weather, gps, vehicle)
        if source and any(key not in _PROVENANCE_FIELDS for key in source)
    ]
    if sources and all(type(source.get("observed_at_ns")) is int
                       and type(source.get("available_at_ns")) is int
                       for source in sources):
        record["observed_at_ns"] = max(source["observed_at_ns"] for source in sources)
        record["available_at_ns"] = max(source["available_at_ns"] for source in sources)
    return record


def _optional_float(value: Any) -> float | None:
    return None if value is None or value == "" else float(value)


def _feature_values(source: dict[str, Any] | None) -> dict[str, Any]:
    return {
        key: value for key, value in (source or {}).items()
        if key not in _PROVENANCE_FIELDS
    }


__all__ = ["build_context_record"]
