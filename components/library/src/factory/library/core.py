"""Game catalog models and scanner interface."""

from __future__ import annotations

from pathlib import Path
from typing import Protocol

from pydantic import BaseModel, Field


class Game(BaseModel, frozen=True):
    """A game in the library catalog."""

    id: str
    title: str
    system: str
    rom_path: Path
    core_hint: str | None = None


class LibraryScanner(Protocol):
    """Protocol for scanning a directory tree and producing a game catalog."""

    def scan(self, root: Path) -> list[Game]: ...


class StubScanner:
    """Placeholder scanner — returns empty catalog. Real impl parses MAME XML / No-Intro DATs."""

    def scan(self, root: Path) -> list[Game]:
        return []
