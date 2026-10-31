"""ROM compatibility checking against local RetroArch cores/BIOS."""

from __future__ import annotations

from enum import Enum
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .ingest import RomCandidate


class CompatStatus(str, Enum):
    OK = "OK"
    MISSING_BIOS = "MISSING_BIOS"
    MISSING_CORE = "MISSING_CORE"
    BAD_ROMSET = "BAD_ROMSET"
    MISSING_CHD = "MISSING_CHD"
    UNKNOWN_SYSTEM = "UNKNOWN_SYSTEM"


# HEURISTIC -- full DAT resolution Phase-3
_EXTENSION_TO_SYSTEM: dict[str, tuple[str, str, str | None]] = {
    # extension -> (system, core_name_stem, bios_file_or_None)
    ".z64": ("n64", "mupen64plus_next", None),
    ".n64": ("n64", "mupen64plus_next", None),
    ".v64": ("n64", "mupen64plus_next", None),
    ".sfc": ("snes", "snes9x", None),
    ".smc": ("snes", "snes9x", None),
    ".nes": ("nes", "mesen", None),
    ".gba": ("gba", "mgba", "gba_bios.bin"),
    ".gbc": ("gbc", "gambatte", None),
    ".gb": ("gb", "gambatte", None),
    ".gen": ("megadrive", "genesis_plus_gx", None),
    ".smd": ("megadrive", "genesis_plus_gx", None),
    ".pce": ("pcengine", "mednafen_pce", "syscard3.pce"),
    ".zip": ("arcade", "mame2003_plus", None),
    ".7z": ("arcade", "mame2003_plus", None),
    ".chd": ("arcade", "mame", None),
    ".iso": ("psx", "pcsx_rearmed", "scph1001.bin"),
    ".bin": ("psx", "pcsx_rearmed", "scph1001.bin"),
    ".cue": ("psx", "pcsx_rearmed", "scph1001.bin"),
    ".cso": ("psp", "ppsspp", None),
    ".pbp": ("psp", "ppsspp", None),
    ".nds": ("nds", "desmume", "bios7.bin"),
    ".gcm": ("gamecube", "dolphin", None),
    ".gcz": ("gamecube", "dolphin", None),
    ".rvz": ("gamecube", "dolphin", None),
    ".wbfs": ("wii", "dolphin", None),
}


class CompatReport(BaseModel, frozen=True):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    candidate: RomCandidate
    status: CompatStatus
    system: str | None = None
    core_hint: str | None = None
    detail: str | None = None


def check_compatibility(
    candidate: RomCandidate,
    cores_dir: Path,
    bios_dir: Path,
) -> CompatReport:
    """Deterministic compat check: extension heuristic + core/BIOS presence."""
    lookup = _EXTENSION_TO_SYSTEM.get(candidate.extension)
    if lookup is None:
        return CompatReport(
            candidate=candidate,
            status=CompatStatus.UNKNOWN_SYSTEM,
            detail=f"No system mapping for {candidate.extension}",
        )

    system, core_stem, bios_file = lookup

    # Check core exists (match by stem — actual suffix varies by OS)
    core_found = any(
        f.stem == core_stem or f.stem.startswith(core_stem + "_libretro")
        for f in cores_dir.iterdir()
        if f.is_file()
    ) if cores_dir.is_dir() else False

    if not core_found:
        return CompatReport(
            candidate=candidate,
            status=CompatStatus.MISSING_CORE,
            system=system,
            core_hint=core_stem,
            detail=f"Core '{core_stem}' not found in {cores_dir}",
        )

    # Check BIOS if required
    if bios_file and not (bios_dir / bios_file).exists():
        return CompatReport(
            candidate=candidate,
            status=CompatStatus.MISSING_BIOS,
            system=system,
            core_hint=core_stem,
            detail=f"BIOS '{bios_file}' not found in {bios_dir}",
        )

    # For disc-based systems, check companion .chd if .cue
    if candidate.extension == ".cue":
        chd_companion = candidate.path.with_suffix(".chd")
        bin_companion = candidate.path.with_suffix(".bin")
        if not chd_companion.exists() and not bin_companion.exists():
            return CompatReport(
                candidate=candidate,
                status=CompatStatus.MISSING_CHD,
                system=system,
                core_hint=core_stem,
                detail="No companion .chd or .bin found for .cue",
            )

    return CompatReport(
        candidate=candidate,
        status=CompatStatus.OK,
        system=system,
        core_hint=core_stem,
    )


def assess_playability(report: CompatReport) -> CompatReport:
    """STUB — Phase-3 seam for framerate/latency/resolution assessment."""
    return report
