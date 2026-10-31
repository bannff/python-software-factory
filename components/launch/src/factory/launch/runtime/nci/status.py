"""NCI GET_STATUS response parser — pure, no IO.

RetroArch GET_STATUS response format (from docs.libretro.com):
  "GET_STATUS PLAYING <system_id>,<game_basename>,crc32=<hex>"
  "GET_STATUS PAUSED <system_id>,<game_basename>,crc32=<hex>"
  "GET_STATUS CONTENTLESS"
None or unrecognized -> UNKNOWN (never raises).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto


class NciState(Enum):
    CONTENTLESS = auto()
    PAUSED = auto()
    PLAYING = auto()
    UNKNOWN = auto()


@dataclass(frozen=True)
class NciStatus:
    state: NciState
    system_id: str | None = None
    game: str | None = None


_STATE_MAP = {
    "PLAYING": NciState.PLAYING,
    "PAUSED": NciState.PAUSED,
    "CONTENTLESS": NciState.CONTENTLESS,
}


def parse_status(raw: str | None) -> NciStatus:
    """Parse a GET_STATUS response into structured NciStatus. Never raises."""
    if raw is None:
        return NciStatus(NciState.UNKNOWN)

    # Strip the "GET_STATUS " prefix if present
    text = raw.strip()
    if text.startswith("GET_STATUS "):
        text = text[len("GET_STATUS "):]

    # First token is the state keyword
    parts = text.split(None, 1)
    if not parts:
        return NciStatus(NciState.UNKNOWN)

    state = _STATE_MAP.get(parts[0])
    if state is None:
        return NciStatus(NciState.UNKNOWN)

    if state == NciState.CONTENTLESS or len(parts) < 2:
        return NciStatus(state)

    # Remainder: "system_id,game_basename,crc32=..." — comma-delimited
    # Defensive: split on comma, take first two fields if present
    fields = parts[1].split(",")
    system_id = fields[0] if len(fields) >= 1 else None
    game = fields[1] if len(fields) >= 2 else None
    return NciStatus(state, system_id=system_id, game=game)
