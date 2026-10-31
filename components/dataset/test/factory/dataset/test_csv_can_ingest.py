"""Contract tests for the public-dataset CSV/TXT ingest adapter.

Covers the Car-Hacking CSV format and the OTIDS / normal_run_data
space-delimited TXT format. Each test parses a tiny inline fixture
and asserts the canonical record schema.
"""

from __future__ import annotations

import json
import textwrap
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.csv_can_ingest import (
    CsvCanIngestStageAdapter,
    _uri_to_path,
)
from factory.dataset.runtime.adapters.csv_can_ingest_formats import (
    iter_csv_frames,
    iter_txt_frames,
)
from factory.dataset.runtime.ports import DatasetStagePort

REQUIRED_FIELDS = {
    "timestamp_ns",
    "timestamp_epoch_s",
    "vehicle_id",
    "trip_id",
    "bus_name",
    "arbitration_id",
    "is_extended",
    "is_fd",
    "dlc",
    "data_bytes",
    "frame_type",
    "error_state",
    "source_ecu",
    "capture_source",
    "decoded_signals",
    "dbc_message_name",
    "source_dataset",
    "source_vehicle",
}


def test_satisfies_stage_port_surface() -> None:
    a = CsvCanIngestStageAdapter()
    assert callable(getattr(a, "execute", None))
    assert a.name == "csv_can_ingest"
    assert a.stage_version
    assert {"csv_paths", "txt_paths", "source_dataset", "source_vehicle"} <= a.allowed_config
    assert hasattr(DatasetStagePort, "execute")


def test_uri_to_path_handles_file_scheme() -> None:
    p = _uri_to_path("file:///tmp/foo.csv")
    assert p == Path("/tmp/foo.csv")
    p = _uri_to_path("/tmp/bar.csv")
    assert p == Path("/tmp/bar.csv")


def test_rejects_empty_config() -> None:
    a = CsvCanIngestStageAdapter()
    with pytest.raises(ValueError, match="non-empty"):
        list(a.execute([], {}))


def test_rejects_unknown_config() -> None:
    a = CsvCanIngestStageAdapter()
    with pytest.raises(ValueError, match="Unsupported"):
        list(a.execute([], {"csv_paths": ["/x"], "junk": 1}))


def test_parses_otids_txt_format(tmp_path: Path) -> None:
    """OTIDS / normal_run_data format with 8 data bytes."""
    txt = tmp_path / "attack_free.txt"
    txt.write_text(textwrap.dedent("""\
        Timestamp:          0.000000        ID: 0316    000    DLC: 8    05 20 ea 0a 20 1a 00 7f
        Timestamp:          0.000224        ID: 0329    000    DLC: 8    d7 a7 7f 8c 11 2f 00 10
        Timestamp:          0.000462        ID: 0080    000    DLC: 8    00 17 ea 0a 20 1a 20 43
    """))
    records = list(iter_txt_frames(
        txt,
        source_dataset="otids",
        source_vehicle="Kia Soul",
        vehicle_id="public_otids",
        max_records=None,
    ))
    assert len(records) == 3
    assert records[0]["arbitration_id"] == "0x316"
    assert records[0]["dlc"] == 8
    assert records[0]["data_bytes"] == "0520ea0a201a007f"
    assert records[0]["timestamp_epoch_s"] == 0.0
    assert records[0]["capture_source"] == "public_otids"
    assert REQUIRED_FIELDS <= set(records[0].keys())


def test_parses_car_hacking_csv_format(tmp_path: Path) -> None:
    """Car-Hacking attack CSV with trailing label column."""
    csv = tmp_path / "DoS_dataset.csv"
    csv.write_text(textwrap.dedent("""\
        Timestamp,ID,DLC,Data0,Data1,Data2,Data3,Data4,Data5,Data6,Data7,Label
        1478198376.389427,0316,8,05,21,68,09,21,21,00,6f,R
        1478198376.389636,018f,8,fe,5b,00,00,00,3c,00,00,T
    """))
    records = list(iter_csv_frames(
        csv,
        source_dataset="car_hacking",
        source_vehicle="Kia Soul",
        vehicle_id="public_car_hacking",
        max_records=None,
    ))
    assert len(records) == 2
    assert records[0]["arbitration_id"] == "0x316"
    assert records[1]["arbitration_id"] == "0x18F"
    assert records[0]["data_bytes"] == "052168092121006f"
    assert records[0]["timestamp_epoch_s"] == pytest.approx(1478198376.389427)


def test_adapter_dispatches_to_both_formats(tmp_path: Path) -> None:
    """End-to-end via the adapter: txt + csv in one execute() call."""
    txt = tmp_path / "free.txt"
    txt.write_text("Timestamp: 1.0  ID: 0100  000  DLC: 2  aa bb\n")
    csv = tmp_path / "attack.csv"
    csv.write_text("Timestamp,ID,DLC,Data0,Data1,Data2,Data3,Data4,Data5,Data6,Data7\n1.5,0200,8,01,02,03,04,05,06,07,08\n")
    a = CsvCanIngestStageAdapter()
    records = list(a.execute([], {
        "txt_paths": [txt.as_uri()],
        "csv_paths": [csv.as_uri()],
        "source_dataset": "public",
        "source_vehicle": "Kia Soul",
    }))
    assert len(records) == 2
    arbs = sorted(r["arbitration_id"] for r in records)
    assert arbs == ["0x100", "0x200"]


def test_max_records_caps_output(tmp_path: Path) -> None:
    txt = tmp_path / "many.txt"
    txt.write_text("\n".join(
        f"Timestamp: {i}.0  ID: 0100  000  DLC: 2  aa bb" for i in range(10)
    ) + "\n")
    records = list(iter_txt_frames(
        txt,
        source_dataset="x", source_vehicle="y", vehicle_id="v", max_records=3,
    ))
    assert len(records) == 3


def test_skips_unparseable_lines(tmp_path: Path) -> None:
    """Garbage lines (header, blank, malformed) are silently dropped."""
    txt = tmp_path / "messy.txt"
    txt.write_text(textwrap.dedent("""\
        # this is a comment
        Timestamp: 1.0  ID: 0100  000  DLC: 2  aa bb
        not a real frame
        Timestamp: 2.0  ID: 0200  000  DLC: 2  cc dd
    """))
    records = list(iter_txt_frames(
        txt,
        source_dataset="x", source_vehicle="y", vehicle_id="v", max_records=None,
    ))
    assert len(records) == 2
    arbs = [r["arbitration_id"] for r in records]
    assert arbs == ["0x100", "0x200"]
