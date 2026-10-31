"""Per-format parsers for public-dataset CAN files.

Split from ``csv_can_ingest.py`` to keep the main adapter under 200
LOC. Each parser is a generator that yields canonical ``can_frame``
records; the dispatch logic in the adapter decides which one to call.

Two formats are supported:

* ``iter_csv_frames``: Car-Hacking-style CSV
  (``timestamp,ID,DLC,d0,d1,d2,d3,d4,d5,d6,d7,label``)
* ``iter_txt_frames``: OTIDS / normal_run_data space-delimited txt
  (``Timestamp: <float>   ID: <hex> <hex>   DLC: <int>   <byte1> ... <byte8>``)
"""

from __future__ import annotations

import csv as _csv
import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

# Whitespace-tolerant: "Timestamp:", "ID:", "DLC:" labels with runs of spaces between.
_TXT_PATTERN = re.compile(
    r"Timestamp:\s*([\d.]+)\s+ID:\s*([0-9a-fA-F]+)\s+\S+\s+DLC:\s*(\d+)\s+"
    r"((?:[0-9a-fA-F]{2}\s+){0,8}[0-9a-fA-F]{2})"
)


def iter_csv_frames(
    csv_path: Path,
    *,
    source_dataset: str,
    source_vehicle: str,
    vehicle_id: str,
    max_records: int | None,
) -> Iterator[dict[str, Any]]:
    """Yield canonical frames from a Car-Hacking-style CSV file.

    Format: ``timestamp,ID,DLC,d0,d1,d2,d3,d4,d5,d6,d7,label``.
    The 9th data column is the optional ``label`` (R/T); absent on
    most non-Car-Hacking CSVs.
    """
    trip_id = csv_path.stem
    n = 0
    with csv_path.open("r", newline="") as f:
        reader = _csv.reader(f)
        for row in reader:
            if not row or row[0].startswith("Timestamp") or row[0].startswith("#"):
                continue
            try:
                ts = float(row[0])
                can_id = row[1].strip().lower()
                if not can_id.startswith("0x"):
                    can_id = f"0x{int(can_id, 16) if all(c in '0123456789abcdefABCDEF' for c in can_id) else int(can_id):X}"
                dlc = int(row[2])
                data_bytes = bytes(int(b, 16) for b in row[3:11])
            except (ValueError, IndexError):
                continue
            yield _build_record(
                ts=ts,
                can_id=can_id,
                dlc=dlc,
                data_bytes=data_bytes,
                trip_id=trip_id,
                vehicle_id=vehicle_id,
                source_dataset=source_dataset,
                source_vehicle=source_vehicle,
            )
            n += 1
            if max_records is not None and n >= max_records:
                return


def iter_txt_frames(
    txt_path: Path,
    *,
    source_dataset: str,
    source_vehicle: str,
    vehicle_id: str,
    max_records: int | None,
) -> Iterator[dict[str, Any]]:
    """Yield canonical frames from an OTIDS / normal_run_data TXT file.

    Format: ``Timestamp: <float>   ID: <hex> <hex>   DLC: <int>   <byte1> ... <byte8>``.
    Lines that don't match the pattern are skipped silently so partially
    corrupt files still produce useful output.
    """
    trip_id = txt_path.stem
    n = 0
    with txt_path.open("r") as f:
        for line in f:
            m = _TXT_PATTERN.search(line)
            if not m:
                continue
            try:
                ts = float(m.group(1))
                can_id = f"0x{int(m.group(2), 16):X}"
                dlc = int(m.group(3))
                data_bytes = bytes(int(b, 16) for b in m.group(4).split())
            except (ValueError, IndexError):
                continue
            yield _build_record(
                ts=ts,
                can_id=can_id,
                dlc=dlc,
                data_bytes=data_bytes,
                trip_id=trip_id,
                vehicle_id=vehicle_id,
                source_dataset=source_dataset,
                source_vehicle=source_vehicle,
            )
            n += 1
            if max_records is not None and n >= max_records:
                return


def _build_record(
    *,
    ts: float,
    can_id: str,
    dlc: int,
    data_bytes: bytes,
    trip_id: str,
    vehicle_id: str,
    source_dataset: str,
    source_vehicle: str,
) -> dict[str, Any]:
    """Translate one CSV/TXT row into the canonical CAN frame record.

    Public-dataset timestamps are Unix epoch seconds (some files start
    at 0). We convert to nanoseconds and also expose the original
    epoch seconds in ``timestamp_epoch_s`` for downstream profiling.
    """
    timestamp_ns = int(ts * 1_000_000_000)
    return {
        "timestamp_ns": timestamp_ns,
        "timestamp_epoch_s": ts,
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "bus_name": "CAN1",
        "arbitration_id": can_id,
        "is_extended": False,
        "is_fd": False,
        "dlc": dlc,
        "data_bytes": data_bytes.hex(),
        "frame_type": "data",
        "error_state": "normal",
        "source_ecu": None,
        "capture_source": f"public_{source_dataset}",
        "decoded_signals": None,
        "dbc_message_name": None,
        "source_dataset": source_dataset,
        "source_vehicle": source_vehicle,
    }
