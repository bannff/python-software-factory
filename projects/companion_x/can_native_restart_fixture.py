"""Tiny exact local CAN and Chronos-2 fixtures for restart acceptance."""
from __future__ import annotations

import hashlib
import json
from importlib.metadata import version as package_version
from pathlib import Path

from asammdf import MDF, Signal
import numpy as np
import torch
from chronos import Chronos2Pipeline
from chronos.chronos2.config import Chronos2CoreConfig
from chronos.chronos2.model import Chronos2Model

from factory.machine_learning.runtime.adapters.chronos_identity import MODEL_REVISION
from factory.machine_learning.runtime.adapters.chronos_pipeline import save_backbone
from factory.machine_learning.runtime.chronos_acquisition import validate_chronos_backbone_ref
from factory.machine_learning.runtime.chronos_acquisition_evidence import (
    ACQUISITION_FILENAME, acquisition_document,
)
from factory.machine_learning.runtime.passport_config import resolve_chronos_roots
from factory.machine_learning.runtime.passport_tree_seal import seal_read_only_tree
from factory.machine_learning.runtime.passport_trees import chronos_backbone_artifact_ref
from factory.machine_learning.runtime.passport_validation import canonical_json
from factory.machine_learning.runtime.ports import TimeSeriesModelConfig

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


def write_can_fixture(root: Path) -> tuple[Path, dict]:
    """Write an approved catalog plus a real three-fingerprint MF4 capture."""
    dataset_root = root / "passports" / "datasets"
    artifacts = dataset_root / "dbc_catalog" / "artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    dbc = artifacts / "fixture.dbc"
    dbc.write_text(DBC_TEXT)
    fingerprints = [
        {"arbitration_id": value, "dlc": 8, "is_extended": False}
        for value in (256, 257, 258)
    ]
    entry = {
        "catalog_id": "fixture-can", "version": "1.0.0",
        "provenance": {
            "source_url": "https://example.invalid/fixture.dbc",
            "artifact_uri": dbc.resolve().as_uri(),
            "source_kind": "approved_manifest", "spdx_license": "CC-BY-4.0",
            "retrieved_at": "2026-01-01T00:00:00Z",
            "sha256": hashlib.sha256(dbc.read_bytes()).hexdigest(),
            "parser_name": "cantools", "parser_version": package_version("cantools"),
            "validation_status": "approved",
        },
        "vehicle": {"make": "Fixture", "model": "Car", "years": [2026],
                    "aliases": ["fixture-car"]},
        "message_fingerprints": fingerprints,
    }
    (dataset_root / "dbc_catalog" / "manifest.json").write_text(
        json.dumps({"entries": [entry]}),
    )
    capture = root / "capture"
    capture.mkdir(parents=True)
    _write_mf4(capture / "capture.mf4")
    return capture, entry


def _write_mf4(path: Path) -> None:
    dtype = np.dtype([
        ("CAN_DataFrame.BusChannel", "<u1"), ("CAN_DataFrame.ID", "<u4"),
        ("CAN_DataFrame.IDE", "<u1"), ("CAN_DataFrame.DLC", "<u1"),
        ("CAN_DataFrame.DataBytes", "<u1", (8,)),
    ])
    rows, timestamps = [], []
    for index in range(24):
        rpm, temp = 1000 + index * 40, 70 + index
        speed, throttle = 25 + index, 10 + index * 0.5
        raw_speed = int(speed * 10)
        payloads = (
            (256, bytes((rpm & 255, rpm >> 8, temp + 40, 0, 0, 0, 0, 0))),
            (257, bytes((raw_speed & 255, raw_speed >> 8, 0, 0, 0, 0, 0, 0))),
            (258, bytes((int(throttle / 0.5), 0, 0, 0, 0, 0, 0, 0))),
        )
        for arbitration_id, payload in payloads:
            rows.append((1, arbitration_id, 0, 8, np.frombuffer(payload, dtype=np.uint8)))
            timestamps.append(float(index * 1000))
    samples, times = np.array(rows, dtype=dtype), np.array(timestamps, dtype=float)
    writer = MDF(version="4.10")
    try:
        writer.append([
            Signal(samples=times, timestamps=times, name="Timestamp"),
            Signal(samples=samples, timestamps=times, name="CAN_DataFrame"),
        ], common_timebase=True)
        writer.save(path, overwrite=True)
    finally:
        writer.close()


def sealed_chronos_config(passport_root: Path) -> dict:
    """Serialize a tiny exact Chronos2 backbone into the production CAS shape."""
    roots = resolve_chronos_roots(passport_root)
    with torch.random.fork_rng():
        torch.manual_seed(0)
        model = Chronos2Model(Chronos2CoreConfig(
            d_model=2, d_kv=2, d_ff=4, num_layers=1, num_heads=1,
            dropout_rate=0.0, chronos_config={
                "context_length": 10, "output_patch_size": 2,
                "input_patch_size": 2, "input_patch_stride": 2,
                "quantiles": [0.1, 0.5, 0.9],
            },
        ))
    model.config._commit_hash = MODEL_REVISION
    staging = roots.backbone_root / ".fixture.staging"
    save_backbone(Chronos2Pipeline(model), staging)
    (staging / ACQUISITION_FILENAME).write_bytes(
        canonical_json(acquisition_document(MODEL_REVISION)),
    )
    provisional = chronos_backbone_artifact_ref("backbone", staging, roots.trust_root)
    destination = roots.backbone_root / provisional.digest
    staging.rename(destination)
    ref = chronos_backbone_artifact_ref("backbone", destination, roots.trust_root)
    seal_read_only_tree(destination)
    validate_chronos_backbone_ref(ref, roots.trust_root)
    return TimeSeriesModelConfig(local_backbone_ref=ref).model_dump(mode="json")


__all__ = ["sealed_chronos_config", "write_can_fixture"]
