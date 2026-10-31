"""View-model dataclasses exposed in the base's public API.

The wall (``projects/openarcade/wall``) is not on the static-import path the
foreman guardian checks, so the base defines shape-compatible ``GameTile`` and
``ControlsVM`` dataclasses here. The wall continues to define its own
versions; both sides must keep the field shape in sync.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GameTile:
    id: str
    title: str
    system: str
    art_url: str
    art_name: str | None = None
    video_url: str = ""
    expected_snap_path: str = ""
    playable: bool = True
    status_detail: str | None = None
    players: str = ""
    genre: str = ""
    year: str = ""
    publisher: str = ""
    rom_path: str = ""
    core: str | None = None
    description: str | None = None
    developer: str | None = None
    release_date: str | None = None
    rating: str | None = None
    category: str | None = None
    screenshots: tuple[str, ...] = ()
    last_played: str | None = None
    play_count: int | None = None


@dataclass(frozen=True)
class ControlsVM:
    runahead_enabled: bool
    runahead_frames: int
    shader_enabled: bool
    shader_name: str
    video_smooth: bool
    core: str
    remap_rows: tuple[tuple[str, str], ...] | None = None


__all__ = ["GameTile", "ControlsVM"]
