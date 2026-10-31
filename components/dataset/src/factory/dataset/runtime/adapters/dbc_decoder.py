"""Shared ordered multi-DBC parser/decoder used by MF4 and public ingest."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..dbc_resolver import (
    ResolvedDbc, resolve_explicit_dbc, reverify_bound_dbc,
)
from ..dbc_semantics import DbcSignalDefinition, DbcVersionDefinition


@dataclass(frozen=True)
class DecodeResult:
    signals: dict[str, float] | None
    message_name: str | None
    sender: str | None
    definition: DbcVersionDefinition | None
    signal_definitions: tuple[DbcSignalDefinition, ...] = ()


class DbcDecoderService:
    """Parse each ordered DBC once; first definition wins overlapping IDs."""

    def __init__(self, resolved: tuple[ResolvedDbc, ...]) -> None:
        if not resolved:
            raise ValueError("DBC decoder requires at least one verified DBC")
        from cantools.database import load_file

        self.resolved = resolved
        self._messages: dict[tuple[int, bool], tuple[Any, DbcVersionDefinition, tuple[DbcSignalDefinition, ...]]] = {}
        for item in resolved:
            database = load_file(str(item.path), strict=False)
            definitions = {
                (message.arbitration_id, message.is_extended): message
                for message in item.definition.messages
            }
            for message in database.messages:
                key = (message.frame_id, bool(message.is_extended_frame))
                definition = definitions[key]
                self._messages.setdefault(key, (message, item.definition, definition.signals))

    @classmethod
    def from_paths(cls, paths: list[str]) -> "DbcDecoderService":
        return cls(tuple(resolve_explicit_dbc(Path(path)) for path in paths))

    @classmethod
    def from_verified_definition(
        cls, path: str, definition: dict[str, Any],
    ) -> "DbcDecoderService":
        return cls((reverify_bound_dbc(Path(path), definition),))

    @property
    def n_messages(self) -> int:
        return len(self._messages)

    @property
    def definitions(self) -> tuple[DbcVersionDefinition, ...]:
        return tuple(item.definition for item in self.resolved)

    def decode(self, can_id: int, is_extended: bool, data: bytes) -> DecodeResult:
        selected = self._messages.get((can_id, is_extended))
        if selected is None:
            return DecodeResult(None, None, None, None)
        message, definition, signals = selected
        try:
            decoded = message.decode(data[:message.length])
            values = {name: float(value) for name, value in decoded.items()}
        except Exception:
            return DecodeResult(None, None, None, definition)
        sender = message.senders[0] if message.senders else None
        return DecodeResult(values, message.name, sender, definition, signals)

    def try_decode(
        self, can_id: int, is_extended: bool, data: bytes,
    ) -> tuple[dict | None, str | None, str | None]:
        result = self.decode(can_id, is_extended, data)
        return result.signals, result.message_name, result.sender


__all__ = ["DbcDecoderService", "DecodeResult"]
