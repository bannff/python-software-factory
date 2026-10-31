"""Arcade configuration models."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel


class SystemCoreMapping(BaseModel, frozen=True):
    """Maps a system to its default RetroArch core."""

    system: str
    core_path: Path


class ArcadeConfig(BaseModel, frozen=True):
    """Top-level arcade system configuration."""

    nci_host: str = "127.0.0.1"
    nci_port: int = 55355
    retroarch_path: Path = Path("/usr/bin/retroarch")
    roms_root: Path = Path("/roms")
    cores_root: Path = Path("/usr/lib/libretro")
    system_cores: tuple[SystemCoreMapping, ...] = ()
