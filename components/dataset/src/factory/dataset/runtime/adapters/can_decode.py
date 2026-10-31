"""Per-frame MF4 sample → canonical ``can_frame`` record translation.

Split out of ``can_ingest.py`` (LOC tenet): the ingest adapter owns MDF
group iteration; this module owns single-sample decoding against the DBC.
"""

from __future__ import annotations

from typing import Any


def build_record(sample, timestamp_ns: int, trip_id: str, vehicle_id: str, db) -> dict[str, Any]:
    """Translate one MDF structured sample into the canonical CAN frame record."""
    bus_channel = int(sample["CAN_DataFrame.BusChannel"])
    arbitration_id = int(sample["CAN_DataFrame.ID"])
    is_extended = bool(int(sample["CAN_DataFrame.IDE"]))
    dlc = int(sample["CAN_DataFrame.DLC"])
    raw_bytes = bytes(sample["CAN_DataFrame.DataBytes"])

    # CAN FD flags: present only on groups that captured FD frames.
    is_fd = bool(int(sample["CAN_DataFrame.EDL"])) if "CAN_DataFrame.EDL" in sample.dtype.names else False

    decoded_signals, dbc_message_name, source_ecu, dbc_meta = _decode_payload(
        db, arbitration_id, is_extended, raw_bytes,
    )

    return {
        "timestamp_ns": timestamp_ns,
        "vehicle_id": vehicle_id,
        "trip_id": trip_id,
        "bus_name": f"CAN{bus_channel}",
        "arbitration_id": f"0x{arbitration_id:X}",
        "is_extended": is_extended,
        "is_fd": is_fd,
        "dlc": dlc,
        "data_bytes": raw_bytes.hex(),
        "frame_type": "data",
        "error_state": "normal",
        "source_ecu": source_ecu,
        "capture_source": "mf4",
        "decoded_signals": decoded_signals,
        "dbc_message_name": dbc_message_name,
        **dbc_meta,
    }


def _decode_payload(
    decoder, arbitration_id: int, is_extended: bool, raw_bytes: bytes,
) -> tuple[dict | None, str | None, str | None, dict[str, Any]]:
    if hasattr(decoder, "decode"):
        result = decoder.decode(arbitration_id, is_extended, raw_bytes)
        definition = result.definition
        metadata: dict[str, Any] = {}
        if definition is not None:
            provenance = definition.provenance.model_dump(mode="json")
            metadata = {
                "dbc_definition_id": definition.definition_id,
                "dbc_catalog_id": definition.catalog_id,
                "dbc_version": definition.version,
                "dbc_digest": definition.digest,
                "dbc_source_uri": provenance["source_url"],
                "dbc_artifact_uri": provenance["artifact_uri"],
                "dbc_source_kind": provenance["source_kind"],
                "dbc_spdx_license": provenance["spdx_license"],
                "dbc_retrieved_at": provenance["retrieved_at"],
                "dbc_parser_name": provenance["parser_name"],
                "dbc_parser_version": provenance["parser_version"],
                "dbc_validation_status": provenance["validation_status"],
                "dbc_provenance": provenance,
                "decoded_signal_definitions": [
                    signal.model_dump(mode="json") for signal in result.signal_definitions
                ],
            }
        return result.signals, result.message_name, result.sender, metadata
    signals, name, sender = try_decode(decoder, arbitration_id, is_extended, raw_bytes)
    return signals, name, sender, {}


def try_decode(
    db,
    arbitration_id: int,
    is_extended: bool,
    raw_bytes: bytes,
) -> tuple[dict | None, str | None, str | None]:
    """Decode one frame using the DBC; return (signals, message_name, sender) or (None, None, None)."""
    try:
        message = db.get_message_by_frame_id(arbitration_id, force_extended_id=is_extended)
    except (KeyError, ValueError):
        return None, None, None
    if message is None:
        return None, None, None
    try:
        decoded = message.decode(raw_bytes[: message.length])
    except Exception:
        return None, None, None
    sender = message.senders[0] if message.senders else None
    return {name: float(value) for name, value in decoded.items()}, message.name, sender
