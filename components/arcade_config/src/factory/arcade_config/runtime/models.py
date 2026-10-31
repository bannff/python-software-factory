"""Immutable value objects for the RetroArch config control-plane.

Pure domain — no IO, no framework imports.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from pathlib import Path


class Scope(Enum):
    """Override precedence scope (most specific wins)."""

    GLOBAL = "global"
    CORE = "core"
    CONTENT_DIR = "content_dir"
    GAME = "game"


# Canonical RetroPad button names per libretro specification.
RETROPAD_BUTTONS: frozenset[str] = frozenset(
    ("b", "y", "select", "start", "up", "down", "left", "right",
     "a", "x", "l", "r", "l2", "r2", "l3", "r3")
)


@dataclass(frozen=True, slots=True)
class CoreOption:
    """A single core option with its value constrained to allowed choices."""

    key: str
    value: str
    allowed: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.value not in self.allowed:
            raise ValueError(
                f"CoreOption '{self.key}': value {self.value!r} not in allowed {self.allowed}"
            )


@dataclass(frozen=True, slots=True)
class RawOption:
    """An uncurated core option — value displayed read-only, no allowed constraint."""

    key: str
    value: str


@dataclass(frozen=True, slots=True)
class InputRemap:
    """Maps a RetroPad button to a core input target."""

    retropad_button: str
    target: str

    def __post_init__(self) -> None:
        if self.retropad_button not in RETROPAD_BUTTONS:
            raise ValueError(
                f"Unknown RetroPad button: {self.retropad_button!r}. "
                f"Valid: {sorted(RETROPAD_BUTTONS)}"
            )
        if self.target not in RETROPAD_BUTTONS:
            raise ValueError(
                f"Invalid remap target: {self.target!r}. "
                f"Valid: {sorted(RETROPAD_BUTTONS)}"
            )


@dataclass(frozen=True, slots=True)
class ShaderPreset:
    """Reference to a shader preset file (.slangp/.glslp/.cgp)."""

    path: Path


@dataclass(frozen=True, slots=True)
class RunAheadConfig:
    """Run-ahead latency reduction config (file-set only; toggle live via NCI)."""

    enabled: bool
    frames: int = 1
