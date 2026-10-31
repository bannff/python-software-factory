"""MF4 ingest + DBC decode adapter for the CAN failure-prediction pipeline.

This is the first CAN-specific stage adapter. It reads MDF 4.11 binary
captures (``asammdf``), decodes classic CAN data frames with the Toyota
Legacy DBC (``cantools``), and yields canonical ``can_frame`` records
matching the dataset brick's ``record_schema="can_frame"`` contract.

Design notes
------------
* Each MDF file has many groups; most are empty metadata siblings of the
  one real bus. We probe each group with the structured ``CAN_DataFrame``
  parent and skip groups that yield zero samples or belong to
  ``CAN_ErrorFrame`` / ``CAN_RemoteFrame`` channels.
* The DBC has overlapping signal definitions (Toyota quirk); we use
  ``strict=False`` to accept the parse and fall back to raw hex bytes
  for arbitration IDs that fail to decode.
* Timestamps are stored as raw microseconds and converted to nanoseconds
  for the canonical record (matches downstream time-series tooling).
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
import json
from pathlib import Path
from typing import Any

from .can_decode import build_record
from .dbc_decoder import DbcDecoderService
from ..mf4_probe import iter_mf4_can_samples


class CanIngestStageAdapter:
    """Adapter that converts MF4 captures into canonical CAN frame records.

    Implements ``DatasetStagePort`` so it slots into the recipe stage map
    alongside the Agentic-Datasets adapters. The ``name`` matches the
    recipe stage ID and ``stage_version`` is a stable identifier for
    checkpoint lineage.
    """

    name = "can_ingest"
    stage_version = "factory-can-ingest-1"
    allowed_config = frozenset({"mf4_paths", "dbc_path", "dbc_definition", "vehicle_id"})

    def __init__(
        self,
        dbc_path: str | None = None,
        *,
        db=None,
    ) -> None:
        # ``db`` is an optional pre-loaded cantools database, used by tests
        # to avoid re-parsing the DBC on every instantiation.
        self._explicit_dbc_path = dbc_path
        self._db = db
        self._active_db_key: tuple[str, str] | None = None
        self._active_db = None

    def _resolve_db(self, config: Mapping[str, Any]):
        """Load or reuse a decoder bound to both path and verified definition."""
        if self._db is not None:
            return self._db
        config_dbc = (config or {}).get("dbc_path")
        target = config_dbc or self._explicit_dbc_path
        if target is None:
            raise ValueError("can_ingest requires 'dbc_path' config or pre-loaded db")
        definition = (config or {}).get("dbc_definition")
        identity = json.dumps(definition, sort_keys=True, separators=(",", ":")) \
            if definition is not None else ""
        key = (str(target), identity)
        if self._active_db is not None and self._active_db_key == key:
            return self._active_db
        self._active_db = (
            DbcDecoderService.from_verified_definition(str(target), definition)
            if definition is not None
            else DbcDecoderService.from_paths([str(target)])
        )
        self._active_db_key = key
        return self._active_db

    def execute(
        self,
        records: Iterable[Any],
        config: Mapping[str, Any] | None = None,
    ) -> Iterator[dict[str, Any]]:
        """Yield canonical CAN frame records for every data frame in the inputs.

        ``records`` is ignored; the adapter sources its data from
        ``config["mf4_paths"]`` (list of MF4 files) and ``config["dbc_path"]``.
        Keeping the iterable parameter honors the ``DatasetStagePort``
        protocol so the recipe executor can chain this stage naturally.
        """
        values = dict(config or {})
        unknown = set(values) - self.allowed_config
        if unknown:
            raise ValueError(f"Unsupported can_ingest configuration: {sorted(unknown)}")

        mf4_paths: list[str] = values.get("mf4_paths") or []
        if not mf4_paths:
            raise ValueError("can_ingest requires non-empty 'mf4_paths' config")
        if not values.get("dbc_path") and self._explicit_dbc_path is None and self._db is None:
            raise ValueError("can_ingest requires 'dbc_path' config or pre-loaded db")

        # ``records`` is consumed only to materialize the upstream iterable
        # contract — we emit our own frames sourced from MF4.
        for _ in records:
            pass

        db = self._resolve_db(values)
        for mf4_uri in mf4_paths:
            # Convert file:// URIs to local paths for asammdf
            if mf4_uri.startswith("file://"):
                from ..recipe import path_from_uri
                mf4_path = str(path_from_uri(mf4_uri))
            else:
                mf4_path = mf4_uri
            yield from _iter_mf4_frames(mf4_path, db, vehicle_id=values.get("vehicle_id", "local"))


def _iter_mf4_frames(
    mf4_path: str,
    db,
    *,
    vehicle_id: str,
) -> Iterator[dict[str, Any]]:
    """Yield canonical CAN frame records for one MF4 file."""
    for sample, timestamp_ns, trip_id in iter_mf4_can_samples(Path(mf4_path)):
        try:
            yield build_record(sample, timestamp_ns, trip_id, vehicle_id, db)
        except (ValueError, KeyError, IndexError):
            continue
