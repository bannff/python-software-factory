"""Single parser for canonical DBC definitions and semantic role inference."""
from __future__ import annotations

from pathlib import Path

from .dbc_identity import dbc_message_identity, dbc_signal_identity, dbc_version_identity
from .dbc_models import DbcArtifactProvenance
from .dbc_semantics import DbcMessageDefinition, DbcSignalDefinition, DbcVersionDefinition

_ROLE_TOKENS = {
    "rotational_speed": ("rpm", "engine_speed", "enginespeed", "shaft_speed"),
    "vehicle_speed": ("vehicle_speed", "vehiclespeed", "wheel_speed", "speed_kph"),
    "thermal_state": ("coolant", "temperature", "temp"),
    "command": ("command", "throttle", "pedal", "target"),
    "response": ("response", "rpm", "engine_speed", "enginespeed", "actual"),
}


def infer_semantic_roles(name: str) -> tuple[str, ...]:
    normalized = name.casefold().replace("-", "_").replace(" ", "_")
    return tuple(sorted(
        role for role, aliases in _ROLE_TOKENS.items()
        if any(alias in normalized for alias in aliases)
    ))


def parse_dbc_definition(
    path: Path, provenance: DbcArtifactProvenance, *, catalog_id: str, version: str,
) -> DbcVersionDefinition:
    """Parse verified bytes through cantools into an immutable semantic definition."""
    from cantools.database import load_file

    db = load_file(str(path), strict=False)
    messages = []
    for message in sorted(db.messages, key=lambda item: (
        item.frame_id, bool(item.is_extended_frame), item.name,
    )):
        message_id = dbc_message_identity(
            provenance.sha256, message.frame_id, bool(message.is_extended_frame),
        )
        signals = tuple(_signal(provenance.sha256, message_id, message, signal)
                        for signal in sorted(message.signals, key=lambda item: (item.start, item.name)))
        messages.append(DbcMessageDefinition(
            message_id=message_id, name=message.name,
            arbitration_id=message.frame_id,
            is_extended=bool(message.is_extended_frame), dlc=message.length,
            senders=tuple(sorted(message.senders or ())), signals=signals,
        ))
    if not messages:
        raise ValueError("DBC parser produced no messages")
    return DbcVersionDefinition(
        definition_id=dbc_version_identity(provenance.sha256),
        catalog_id=catalog_id, version=version, digest=provenance.sha256,
        provenance=provenance, messages=tuple(messages),
    )


def _signal(sha256: str, message_id: str, message, signal) -> DbcSignalDefinition:
    return DbcSignalDefinition(
        signal_id=dbc_signal_identity(
            sha256, message.frame_id, signal.name, bool(message.is_extended_frame),
        ),
        name=signal.name, start_bit=signal.start, length_bits=signal.length,
        byte_order=signal.byte_order, is_signed=signal.is_signed,
        scale=float(signal.scale), offset=float(signal.offset),
        minimum=None if signal.minimum is None else float(signal.minimum),
        maximum=None if signal.maximum is None else float(signal.maximum),
        unit=signal.unit or "", receivers=tuple(sorted(signal.receivers or ())),
        semantic_roles=infer_semantic_roles(signal.name),
    )


__all__ = ["infer_semantic_roles", "parse_dbc_definition"]
