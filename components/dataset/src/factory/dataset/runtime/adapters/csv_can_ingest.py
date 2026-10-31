"""Public-dataset CAN ingest adapter (CSV + space-delimited TXT).

This is the public-datasets counterpart to ``can_ingest`` (which only
handles MF4). It reads the two common formats used in the public CAN
IDS literature:

* Car-Hacking attack CSVs (Hacking/Counter Measurement Lab, Korea)::

      timestamp,ID,DLC,d0,d1,d2,d3,d4,d5,d6,d7,label

* OTIDS + Car-Hacking ``normal_run_data`` space-delimited txt::

      Timestamp: 1479121434.850202        ID: 0350    000    DLC: 8    05 28 84 66 6d 00 00 a2

The adapter yields canonical ``can_frame`` records matching the dataset
brick's ``record_schema="can_frame"`` contract (same field set as
``can_ingest``). DBC decoding is **optional**: when ``dbc_path`` (or
``dbc_paths``) is supplied, the raw bytes are decoded using the
provided DBC — typically the Hyundai 2015 CCAN/MCAN pair, which
overlaps enough with the Kia Soul public-data bus to recover a
useful signal set. Without a DBC, the adapter runs in raw-bytes
mode and ``decoded_signals`` stays ``None`` for every record.

Provenance is carried via ``source_dataset`` + ``source_vehicle`` in
the config so the combined JSONL stays auditable.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from pathlib import Path
from typing import Any

from .dbc_decoder import DbcDecoderService
from .csv_can_ingest_formats import iter_csv_frames, iter_txt_frames


class CsvCanIngestStageAdapter:
    """Adapter that converts public-dataset CSV/TXT into canonical CAN frames.

    Implements ``DatasetStagePort`` so it slots into the recipe stage
    map alongside ``can_ingest``. ``name = "csv_can_ingest"`` keeps it
    distinct so the recipe resolver can pick the right adapter per
    input format.
    """

    name = "csv_can_ingest"
    stage_version = "factory-csv-can-ingest-2"
    allowed_config = frozenset(
        {
            "csv_paths",
            "txt_paths",
            "source_dataset",
            "source_vehicle",
            "vehicle_id",
            "max_records",
            "dbc_path",
            "dbc_paths",
        }
    )

    def __init__(self) -> None:
        # DBC decoder cache: list of paths → MultiDbcDecoder. We re-use
        # the same decoder across files in a single run to avoid the
        # ~0.5s cost of re-parsing the DBC per CSV/TXT file.
        self._decoder_cache: dict[tuple[str, ...], DbcDecoderService] = {}

    def _resolve_decoder(self, dbc_paths: list[str]) -> DbcDecoderService | None:
        """Return a cached shared decoder for the ordered DBC path list."""
        if not dbc_paths:
            return None
        key = tuple(Path(p).as_posix() for p in dbc_paths)
        decoder = self._decoder_cache.get(key)
        if decoder is None:
            decoder = DbcDecoderService.from_paths(list(dbc_paths))
            self._decoder_cache[key] = decoder
        return decoder

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield canonical CAN frame records for every CSV/TXT input."""
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(
                f"Unsupported csv_can_ingest configuration: {sorted(unknown)}"
            )

        csv_paths: list[str] = list(values.get("csv_paths") or [])
        txt_paths: list[str] = list(values.get("txt_paths") or [])
        if not csv_paths and not txt_paths:
            raise ValueError(
                "csv_can_ingest requires non-empty 'csv_paths' or 'txt_paths' config"
            )

        for _ in records:
            pass  # honor DatasetStagePort contract

        source_dataset = values.get("source_dataset", "public")
        source_vehicle = values.get("source_vehicle", "unknown")
        vehicle_id = values.get("vehicle_id", source_vehicle)
        max_records = values.get("max_records")

        # Collect DBC paths from either singular or plural config key.
        dbc_paths: list[str] = []
        if values.get("dbc_path"):
            dbc_paths.append(values["dbc_path"])
        if values.get("dbc_paths"):
            dbc_paths.extend(values["dbc_paths"])
        decoder = self._resolve_decoder(dbc_paths)

        for csv_uri in csv_paths:
            yield from _apply_decoder(
                iter_csv_frames(
                    _uri_to_path(csv_uri),
                    source_dataset=source_dataset,
                    source_vehicle=source_vehicle,
                    vehicle_id=vehicle_id,
                    max_records=max_records,
                ),
                decoder,
            )

        for txt_uri in txt_paths:
            yield from _apply_decoder(
                iter_txt_frames(
                    _uri_to_path(txt_uri),
                    source_dataset=source_dataset,
                    source_vehicle=source_vehicle,
                    vehicle_id=vehicle_id,
                    max_records=max_records,
                ),
                decoder,
            )


def _apply_decoder(
    records: Iterator[dict[str, Any]],
    decoder: DbcDecoderService | None,
) -> Iterator[dict[str, Any]]:
    """Yield records with ``decoded_signals`` populated when possible.

    If ``decoder`` is None (no DBC supplied) records are passed through
    unchanged — the upstream parser already wrote ``decoded_signals=None``.
    """
    if decoder is None:
        yield from records
        return
    for rec in records:
        try:
            arb_int = int(rec["arbitration_id"], 16)
        except (ValueError, TypeError):
            yield rec
            continue
        raw = bytes.fromhex(rec["data_bytes"])
        result = decoder.decode(arb_int, False, raw)
        if result.signals is not None:
            rec["decoded_signals"] = result.signals
            rec["dbc_message_name"] = result.message_name
            rec["source_ecu"] = result.sender
            if result.definition is not None:
                rec.update({
                    "dbc_definition_id": result.definition.definition_id,
                    "dbc_version": result.definition.version,
                    "dbc_digest": result.definition.digest,
                    "decoded_signal_definitions": [
                        signal.model_dump(mode="json") for signal in result.signal_definitions
                    ],
                })
        yield rec


def _uri_to_path(uri: str) -> Path:
    """Convert a file:// URI or plain path to a Path."""
    if uri.startswith("file://"):
        return Path(uri[len("file://") :])
    return Path(uri)
