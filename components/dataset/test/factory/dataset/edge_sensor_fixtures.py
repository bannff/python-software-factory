"""Shared valid record and payload builders for edge sensor tests."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def sensor_payload(
    *, timestamps: list[int] | None = None,
    channels: list[str] | None = None,
    rows: list[list[int | float]] | None = None,
) -> bytes:
    timestamps = timestamps or [1000, 2000]
    channels = channels or ["accel_x"]
    rows = rows or [[0], [1]]
    return json.dumps({
        "schema_version": "1.0",
        "modality": "imu",
        "channels": channels,
        "samples": [
            {"timestamp_ms": timestamp, "values": values}
            for timestamp, values in zip(timestamps, rows, strict=True)
        ],
    }, allow_nan=True).encode()


def sensor_record(
    record_id: str,
    group_id: str,
    split: str,
    *,
    uri: str | None = None,
    payload: bytes | None = None,
    **overrides,
) -> dict:
    uri = uri or f"file:///windows/{record_id}.json"
    payload = payload if payload is not None else sensor_payload()
    return {
        "schema_version": "1.0",
        "record_id": record_id,
        "task": "sensor-failure",
        "modality": "imu",
        "input_ref": {
            "uri": uri,
            "sha256": hashlib.sha256(payload).hexdigest(),
        },
        "label": "normal",
        "label_provenance": {
            "method": "event_log",
            "source": "device-event-log-v1",
        },
        "group_id": group_id,
        "split": split,
        "observed_through_ms": 2000,
        "label_start_ms": 3000,
        "label_end_ms": 4000,
        **overrides,
    }


def stored_sensor_record(
    root: Path, record_id: str, group_id: str, split: str,
    *, payload: bytes | None = None,
) -> dict:
    content = (
        payload if payload is not None else sensor_payload(
            rows=[[len(record_id)], [len(record_id) + 1]],
        )
    )
    source = root / f"{record_id}.window"
    source.write_bytes(content)
    return sensor_record(
        record_id, group_id, split, uri=source.as_uri(), payload=content,
    )
