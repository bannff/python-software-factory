"""Resolve a RetroArch core LIBRARY PATH for a system, platform-aware.

RetroArch's `-L` flag needs a real path to the core shared library
(`*_libretro.dylib` on macOS, `*_libretro.so` on Linux) — NOT a RetroPie-style
core name like "lr-snes9x2002". This module maps a system short-code to the
installed core library on THIS machine.

Pure + injectable: cores dir, extension, and the system->core-stem map can all
be overridden (env or args) so it works on a dev Mac and the Linux cabinet, and
is testable without touching the real filesystem.

Returns "" when no local core library exists — honest, never a fake path.
"""

from __future__ import annotations

import os
import platform
from pathlib import Path

# system short-code -> libretro core stem (the installed core we launch with).
# Only systems we actually support need entries; unknown systems return "".
DEFAULT_CORE_STEMS: dict[str, str] = {
    "snes": "snes9x",
    "sfc": "snes9x",
    "nes": "fceumm",
    "famicom": "fceumm",
    "genesis": "genesis_plus_gx",
    "megadrive": "genesis_plus_gx",
    "gb": "gambatte",
    "gbc": "gambatte",
    "gba": "mgba",
    "n64": "mupen64plus_next",
    "psx": "pcsx_rearmed",
    "arcade": "fbneo",
}


def default_cores_dir() -> Path:
    """Platform default RetroArch cores directory (env override wins)."""
    env = os.environ.get("OPENARCADE_CORES_DIR")
    if env:
        return Path(env)
    if platform.system() == "Darwin":
        return Path.home() / "Library" / "Application Support" / "RetroArch" / "cores"
    # Linux / RetroPie-ish default; cabinet can override via OPENARCADE_CORES_DIR.
    return Path.home() / ".config" / "retroarch" / "cores"


def _core_ext() -> str:
    return ".dylib" if platform.system() == "Darwin" else ".so"


def resolve_core_path(
    system: str,
    *,
    cores_dir: Path | None = None,
    ext: str | None = None,
    core_stems: dict[str, str] | None = None,
) -> str:
    """Return the absolute core-library path for `system`, or "" if not installed.

    The returned path is verified to exist on disk — RetroArch `-L` requires a
    loadable library, so a non-existent path is useless and we return "" instead.
    """
    if not system:
        return ""
    stems = core_stems or DEFAULT_CORE_STEMS
    stem = stems.get(system.lower())
    if not stem:
        return ""
    directory = cores_dir or default_cores_dir()
    lib = directory / f"{stem}_libretro{ext or _core_ext()}"
    return str(lib) if lib.is_file() else ""
