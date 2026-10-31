"""Internal helpers for the context_ingest stage adapter.

Split out of :mod:`context_ingest` to keep that module under the 200 LOC
factory ceiling. Nothing here is part of the public brick surface; it
may change without notice. Per-source fetchers return ``None`` when the
inputs they need are missing — the orchestrator tolerates ``None`` so
a partial configuration still produces a valid canonical record.
"""

from __future__ import annotations

import csv
import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

# Signal-name candidates inside a decoded CAN frame's ``decoded_signals``
# when extracting GPS; common J1939 / OEM names.
_GPS_KEYS = (
    ("GPS_Latitude", "Latitude", "VehLatitude"),
    ("GPS_Longitude", "Longitude", "VehLongitude"),
    ("GPS_Speed", "Speed", "VehSpeed"),
)

VALID_SOURCES = frozenset({
    "weather_openweathermap", "gps_can", "vehicle_metadata",
})


def parse_time_range(time_range: Any) -> tuple[str, str]:
    """Return ISO-8601 ``(start, end)``; default to a single point in time."""
    if not time_range:
        stamp = datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        return stamp, stamp
    if not isinstance(time_range, (list, tuple)) or len(time_range) != 2:
        raise ValueError("time_range must be a (start_iso, end_iso) tuple")
    start, end = str(time_range[0]), str(time_range[1])
    try:
        datetime.fromisoformat(start.replace("Z", "+00:00"))
        datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"time_range entries must be ISO-8601: {exc}") from exc
    return start, end


def fetch_openweathermap(
    location: Any, start: str, end: str, api_key: str | None,
) -> dict[str, Any] | None:
    """Call OpenWeatherMap ``timemachine``. Returns ``None`` on missing inputs or failure."""
    if not api_key or not isinstance(location, (list, tuple)) or len(location) != 2:
        return None
    lat, lon = float(location[0]), float(location[1])
    params = urllib.parse.urlencode({
        "lat": lat, "lon": lon, "appid": api_key, "start": start, "end": end,
    })
    url = f"https://api.openweathermap.org/data/3.0/onecall/timemachine?{params}"
    try:
        # 10s ceiling — historical endpoints can be slow but should not hang.
        with urllib.request.urlopen(url, timeout=10) as resp:  # noqa: S310
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError):
        return None
    return _normalize_owm_payload(payload)


def _normalize_owm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Project only source-supplied weather values onto the canonical shape."""
    data_list = payload.get("data") or []
    if not data_list:
        return {}
    sample = data_list[0]
    result: dict[str, Any] = {}
    if sample.get("temp") is not None:
        result["temp_c"] = float(sample["temp"]) - 273.15
    if sample.get("humidity") is not None:
        result["humidity_pct"] = float(sample["humidity"])
    precipitation = [
        source.get("1h") for source in (sample.get("rain"), sample.get("snow"))
        if isinstance(source, dict) and source.get("1h") is not None
    ]
    if precipitation:
        result["precipitation_mm"] = sum(float(value) for value in precipitation)
    return result


def extract_gps_from_can(input_uri: str | None) -> dict[str, Any] | None:
    """Average lat/lon/speed from decoded CAN signals in the input file."""
    if not input_uri:
        return None
    from ..helpers import load_records_from_uri
    from ..recipe import path_from_uri
    try:
        path = path_from_uri(input_uri)
    except ValueError:
        return None
    records = load_records_from_uri(path.as_uri())
    buckets: list[list[float]] = [[], [], []]
    for rec in records:
        signals = rec.get("decoded_signals") or {}
        for bucket, keys in zip(buckets, _GPS_KEYS):
            for key in keys:
                if key in signals:
                    bucket.append(float(signals[key]))
                    break
    lats, lons, speeds = buckets
    if not lats or not lons:
        return None
    result = {
        "lat": sum(lats) / len(lats),
        "lon": sum(lons) / len(lons),
    }
    if speeds:
        avg_speed = sum(speeds) / len(speeds)
        result.update({
            "avg_speed_kmh": avg_speed,
            "road_type": (
                "urban" if avg_speed < 30 else "rural" if avg_speed < 70 else "highway"
            ),
        })
    timestamps = [
        record.get("timestamp_ns") for record in records
        if type(record.get("timestamp_ns")) is int
    ]
    if timestamps:
        result.update({
            "observed_at_ns": max(timestamps), "available_at_ns": max(timestamps),
        })
    return result


def load_vehicle_metadata(
    input_uri: str | None, vehicle_id: str,
) -> dict[str, Any] | None:
    """Load static vehicle metadata from a JSON or CSV/TSV file."""
    if not input_uri:
        return None
    from ..recipe import path_from_uri
    try:
        path = path_from_uri(input_uri)
    except ValueError:
        return None
    if not path.exists():
        return None
    suffix = path.suffix.lower()
    if suffix == ".json":
        with path.open() as fh:
            data: Any = json.load(fh)
    elif suffix in {".csv", ".tsv"}:
        delim = "\t" if suffix == ".tsv" else ","
        with path.open(newline="") as fh:
            data = list(csv.DictReader(fh, delimiter=delim))
    else:
        return None
    return _select_vehicle_row(data, vehicle_id)


def _select_vehicle_row(data: Any, vehicle_id: str) -> dict[str, Any] | None:
    """Pick the row for ``vehicle_id`` from list-of-dicts, dict-of-dicts, or single dict."""
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict) and str(row.get("vehicle_id")) == vehicle_id:
                return _normalize_vehicle_row(row)
        return None
    if isinstance(data, dict):
        nested = data.get(vehicle_id)
        return _normalize_vehicle_row(nested if isinstance(nested, dict) else data)
    return None


def _normalize_vehicle_row(row: dict[str, Any]) -> dict[str, Any]:
    result = {
        "odometer_km": _optional_float(row.get("odometer_km")),
        "battery_health_pct": _optional_float(row.get("battery_health_pct")),
    }
    for field in ("observed_at_ns", "available_at_ns"):
        if type(row.get(field)) is int:
            result[field] = row[field]
    return result


def _optional_float(value: Any) -> float | None:
    return None if value is None or value == "" else float(value)
