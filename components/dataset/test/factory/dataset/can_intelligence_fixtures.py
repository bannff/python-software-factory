"""Generated local DBC/catalog fixtures for CAN intelligence tests."""
from __future__ import annotations

import hashlib
import json
from importlib.metadata import version as package_version
from pathlib import Path

import numpy as np
import pytest


DBC_TEXT = '''VERSION "1.0"
NS_ :
BS_:
BU_: ECU
BO_ 256 ENGINE: 8 ECU
 SG_ EngineSpeed : 0|16@1+ (1,0) [0|8000] "rpm" ECU
 SG_ CoolantTemp : 16|8@1+ (1,-40) [-40|215] "degC" ECU
BO_ 257 MOTION: 8 ECU
 SG_ VehicleSpeed : 0|16@1+ (0.1,0) [0|250] "km/h" ECU
BO_ 258 COMMAND: 8 ECU
 SG_ ThrottleCommand : 0|8@1+ (0.5,0) [0|100] "%" ECU
'''


def write_catalog(
    root: Path, *, aliases: tuple[str, ...] = ("fixture-car",),
    dbc_text: str = DBC_TEXT, fingerprints: list[dict] | None = None,
) -> tuple[Path, dict]:
    pytest.importorskip("cantools", reason="DBC fixtures require can-test")
    catalog = root / "dbc_catalog"
    artifacts = catalog / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    dbc = artifacts / "fixture.dbc"
    dbc.write_text(dbc_text)
    digest = hashlib.sha256(dbc.read_bytes()).hexdigest()
    entry = {
        "catalog_id": "fixture-can", "version": "1.0.0",
        "provenance": {
            "source_url": "https://example.invalid/fixture.dbc",
            "artifact_uri": dbc.resolve().as_uri(),
            "source_kind": "approved_manifest", "spdx_license": "CC-BY-4.0",
            "retrieved_at": "2026-01-01T00:00:00Z", "sha256": digest,
            "parser_name": "cantools", "parser_version": package_version("cantools"),
            "validation_status": "approved",
        },
        "vehicle": {"make": "Fixture", "model": "Car", "years": [2026],
                    "aliases": list(aliases)},
        "message_fingerprints": fingerprints or [
            {"arbitration_id": 256, "dlc": 8, "is_extended": False},
            {"arbitration_id": 257, "dlc": 8, "is_extended": False},
            {"arbitration_id": 258, "dlc": 8, "is_extended": False},
        ],
    }
    (catalog / "manifest.json").write_text(json.dumps({"entries": [entry]}))
    return dbc, entry


def write_probe_mf4(root: Path, *, constant: bool = False) -> Path:
    """Create a real CAN_DataFrame MF4 with three observed DBC fingerprints."""
    asammdf = pytest.importorskip("asammdf", reason="MF4 fixtures require can-test")
    MDF, Signal = asammdf.MDF, asammdf.Signal
    path = root / "capture.mf4"
    dtype = np.dtype([
        ("CAN_DataFrame.BusChannel", "<u1"),
        ("CAN_DataFrame.ID", "<u4"),
        ("CAN_DataFrame.IDE", "<u1"),
        ("CAN_DataFrame.DLC", "<u1"),
        ("CAN_DataFrame.DataBytes", "<u1", (8,)),
    ])
    rows = []
    timestamps = []
    for index in range(18):
        rpm = 1000 if constant else 1000 + index * 40
        temp = 70 if constant else 70 + index
        speed = 25 if constant else 25 + index
        throttle = 10 if constant else 10 + index * 0.5
        engine = bytes((rpm & 0xFF, rpm >> 8, int(temp + 40), 0, 0, 0, 0, 0))
        motion_raw = int(speed * 10)
        motion = bytes((motion_raw & 0xFF, motion_raw >> 8, 0, 0, 0, 0, 0, 0))
        command = bytes((int(throttle / 0.5), 0, 0, 0, 0, 0, 0, 0))
        for arbitration_id, payload in ((256, engine), (257, motion), (258, command)):
            rows.append((1, arbitration_id, 0, 8, np.frombuffer(payload, dtype=np.uint8)))
            timestamps.append(float(index * 1000))
    samples = np.array(rows, dtype=dtype)
    times = np.array(timestamps, dtype=float)
    writer = MDF(version="4.10")
    try:
        writer.append([
            Signal(samples=times, timestamps=times, name="Timestamp"),
            Signal(samples=samples, timestamps=times, name="CAN_DataFrame"),
        ], common_timebase=True)
        writer.save(path, overwrite=True)
    finally:
        writer.close()
    return path
