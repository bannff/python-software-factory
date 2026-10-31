"""Pure canonical CAN graph projection builder owned by Dataset."""
from __future__ import annotations

import hashlib
import json
from typing import Any

from ..dbc_identity import dbc_signal_identity, dbc_version_identity
from ..ports import GraphProjectionPort


class TaxonomyBuilder:
    """Collect collision-safe entities/relationships, then flush through a port."""

    def __init__(self) -> None:
        self._entities: dict[str, tuple[str, dict[str, Any]]] = {}
        self._rels: dict[tuple[str, str, str], dict[str, Any]] = {}
        self._frame_counts: dict[str, int] = {}

    def absorb(self, rec: dict[str, Any]) -> set[str]:
        vehicle = str(rec.get("vehicle_id") or "")
        trip = str(rec.get("trip_id") or "")
        bus = str(rec.get("bus_name") or "")
        timestamp = int(rec.get("timestamp_ns") or 0)
        arbitration = str(rec.get("arbitration_id") or "")
        arbitration_int = _arbitration_int(arbitration)
        source_ecu = str(rec.get("source_ecu") or "")
        decoded = rec.get("decoded_signals") or {}
        vehicle_id = f"vehicle-{vehicle}" if vehicle else ""
        trip_id = f"trip-{vehicle}-{trip}" if vehicle and trip else ""
        frame_id = self._frame_id(rec)
        tags: set[str] = set(filter(None, (vehicle_id, trip_id, frame_id)))
        if vehicle_id:
            self._entity(vehicle_id, "Vehicle", {"vehicle_id": vehicle})
        if trip_id:
            self._trip(trip_id, trip, vehicle, timestamp)
        bus_id = f"canbus-{vehicle}-{bus}" if vehicle and bus else ""
        if bus_id:
            self._entity(bus_id, "CANBus", {
                "bus_name": bus, "channel": bus, "baud_rate": 0,
                "vehicle_id": vehicle,
            })
            tags.add(bus_id)
        ecu_id = f"ecu-{vehicle}-{source_ecu}" if vehicle and source_ecu else ""
        if ecu_id:
            self._entity(ecu_id, "ECU", {
                "ecu_id": source_ecu, "bus_name": bus,
                "firmware_version": "unknown", "vehicle_id": vehicle,
            })
            tags.add(ecu_id)
        self._entity(frame_id, "Frame", {
            "timestamp_ns": timestamp, "arbitration_id": arbitration,
            "is_extended": bool(rec.get("is_extended", False)),
            "is_fd": bool(rec.get("is_fd", False)), "dlc": int(rec.get("dlc") or 0),
            "frame_type": rec.get("frame_type") or "data", "vehicle_id": vehicle,
            "trip_id": trip, "bus_name": bus, "data_bytes": rec.get("data_bytes") or "",
            "capture_source": rec.get("capture_source") or "",
        })
        if vehicle_id and ecu_id:
            self._rel(vehicle_id, "HAS_ECU", ecu_id, {"bus_name": bus})
        if trip_id:
            self._rel(frame_id, "PART_OF_TRIP", trip_id, {})
        if ecu_id:
            self._rel(ecu_id, "EMITS_FRAME", frame_id, {
                "bus_name": bus, "captured_at_ns": timestamp,
            })
        if isinstance(decoded, dict) and decoded and arbitration_int is not None:
            tags.update(self._signals(rec, decoded, frame_id, arbitration_int, timestamp))
        return tags

    def _frame_id(self, rec: dict[str, Any]) -> str:
        identity = json.dumps({
            key: rec.get(key) for key in (
                "vehicle_id", "trip_id", "timestamp_ns", "bus_name",
                "arbitration_id", "is_extended", "dlc", "data_bytes",
            )
        }, sort_keys=True, separators=(",", ":"))
        base = f"frame-{hashlib.sha256(identity.encode()).hexdigest()}"
        ordinal = self._frame_counts.get(base, 0)
        self._frame_counts[base] = ordinal + 1
        return f"{base}-{ordinal}"

    def _trip(self, identity: str, trip: str, vehicle: str, timestamp: int) -> None:
        current = self._entities.get(identity)
        start = min(timestamp, int(current[1]["start_ts"])) if current else timestamp
        end = max(timestamp, int(current[1]["end_ts"])) if current else timestamp
        self._entity(identity, "Trip", {
            "trip_id": trip, "vehicle_id": vehicle, "start_ts": start, "end_ts": end,
        })

    def _signals(self, rec, decoded, frame_id, arbitration_id, timestamp) -> set[str]:
        provenance = rec.get("dbc_provenance")
        required = {
            "source_url", "artifact_uri", "source_kind", "spdx_license",
            "retrieved_at", "sha256", "parser_name", "parser_version",
            "validation_status",
        }
        if not isinstance(provenance, dict) or required - set(provenance):
            raise ValueError("canonical DBC provenance is required and must be complete")
        digest = str(rec.get("dbc_digest") or "")
        definition_id = str(rec.get("dbc_definition_id") or "")
        catalog_id = str(rec.get("dbc_catalog_id") or "")
        version = str(rec.get("dbc_version") or "")
        if not digest or provenance["sha256"] != digest:
            raise ValueError("canonical DBC provenance digest mismatch")
        if definition_id != dbc_version_identity(digest) or not catalog_id or not version:
            raise ValueError("canonical DBC definition identity is incomplete")
        self._entity(definition_id, "DBCVersion", {
            "definition_id": definition_id, "catalog_id": catalog_id,
            "dbc_version": version, "checksum_sha256": digest,
            "source_uri": provenance["source_url"],
            "artifact_uri": provenance["artifact_uri"],
            "source_kind": provenance["source_kind"],
            "spdx_license": provenance["spdx_license"],
            "retrieved_at": provenance["retrieved_at"],
            "created_at": provenance["retrieved_at"],
            "parser_name": provenance["parser_name"],
            "parser_version": provenance["parser_version"],
            "validation_status": provenance["validation_status"],
        })
        metadata = {item.get("name"): item
                    for item in rec.get("decoded_signal_definitions") or []}
        result = {definition_id}
        for name, value in sorted(decoded.items()):
            spec = metadata.get(name)
            if not isinstance(spec, dict):
                raise ValueError(f"canonical DBC signal definition missing: {name}")
            signal_id = dbc_signal_identity(
                digest, arbitration_id, name, bool(rec.get("is_extended", False)),
            )
            self._entity(signal_id, "Signal", {
                "signal_name": name, "unit": spec.get("unit") or "",
                "min_value": spec.get("minimum"), "max_value": spec.get("maximum"),
                "resolution": spec.get("scale"), "offset": spec.get("offset"),
                "length_bits": spec.get("length_bits"),
                "byte_order": spec.get("byte_order"),
                "dbc_definition_id": definition_id,
                "arbitration_id": rec.get("arbitration_id"),
            })
            self._rel(definition_id, "DEFINES_SIGNAL", signal_id, {})
            self._rel(frame_id, "DECODES_TO", signal_id, {
                "dbc_version": version, "dbc_digest": digest,
                "decode_at_ns": timestamp, "observed_value": float(value),
                "unit": spec.get("unit") or "",
            })
            result.add(signal_id)
        return result

    def _entity(self, identity: str, type_: str, properties: dict[str, Any]) -> None:
        self._entities[identity] = (type_, properties)

    def _rel(self, source: str, type_: str, target: str, properties: dict[str, Any]) -> None:
        self._rels.setdefault((source, type_, target), properties)

    def commit(self, projection: GraphProjectionPort) -> int:
        for identity in sorted(self._entities):
            type_, properties = self._entities[identity]
            projection.add_entity(identity, type_, properties)
        for source, type_, target in sorted(self._rels):
            projection.add_relationship(
                f"{source}|{type_}|{target}", type_, source, target,
                self._rels[(source, type_, target)],
            )
        return len(self._entities)


def _arbitration_int(value: str) -> int | None:
    try:
        return int(value, 0)
    except (TypeError, ValueError):
        return None


__all__ = ["TaxonomyBuilder"]
