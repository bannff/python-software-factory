"""NCI transport protocol — ports and models.

RetroArch Network Control Interface is a UDP text protocol on port 55355.
Commands are newline-terminated ASCII strings: `COMMAND [args...]\\n`.
Most commands are fire-and-forget; some (GET_STATUS, VERSION) return a response.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class NciCommand:
    """A single RetroArch NCI command."""

    name: str
    args: tuple[str, ...] = ()


def to_wire(cmd: NciCommand) -> bytes:
    """Encode an NciCommand to the NCI UDP wire format (UTF-8, newline-terminated)."""
    parts = [cmd.name] + list(cmd.args)
    return (" ".join(parts) + "\n").encode("utf-8")


class NciTransport(Protocol):
    """Protocol for NCI communication."""

    async def send_command(self, cmd: NciCommand) -> None:
        """Fire-and-forget: send command, no response expected."""
        ...

    async def query(self, cmd: NciCommand, timeout: float = 1.0) -> str | None:
        """Send command and await a response datagram. Returns decoded string or None on timeout."""
        ...
