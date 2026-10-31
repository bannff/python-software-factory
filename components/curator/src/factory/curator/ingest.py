"""ROM directory scanning and candidate discovery."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_ROM_EXTENSIONS: frozenset[str] = frozenset({
    ".zip", ".7z", ".chd", ".iso", ".bin", ".cue",
    ".z64", ".n64", ".v64",
    ".sfc", ".smc",
    ".nes",
    ".gba", ".gbc", ".gb",
    ".gen", ".smd",
    ".pce",
    ".cso", ".pbp",
    ".nds",
    ".gcm", ".gcz", ".rvz", ".wbfs",
})


@dataclass(frozen=True)
class RomCandidate:
    path: Path
    filename: str
    extension: str
    size_bytes: int


def scan_rom_directory(root: Path) -> list[RomCandidate]:
    """Walk *root* and return candidates with ROM/CHD extensions."""
    candidates: list[RomCandidate] = []
    if not root.is_dir():
        return candidates
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in _ROM_EXTENSIONS:
            candidates.append(
                RomCandidate(
                    path=p,
                    filename=p.name,
                    extension=p.suffix.lower(),
                    size_bytes=p.stat().st_size,
                )
            )
    return candidates
