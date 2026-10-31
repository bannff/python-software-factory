"""Compatibility name for the shared ordered multi-DBC decoder service."""
from __future__ import annotations

from pathlib import Path

from .dbc_decoder import DbcDecoderService
from ..dbc_resolver import resolve_explicit_dbc


class MultiDbcDecoder(DbcDecoderService):
    """Backward-compatible constructor preserving ordered first-DBC-wins behavior."""

    def __init__(self, dbc_paths: list[str]) -> None:
        super().__init__(tuple(resolve_explicit_dbc(Path(path)) for path in dbc_paths))


__all__ = ["MultiDbcDecoder"]
