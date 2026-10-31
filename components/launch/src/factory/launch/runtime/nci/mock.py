"""Mock NCI transport — in-process test double that records commands."""

from __future__ import annotations

from .ports import NciCommand, NciTransport


class MockNciTransport:
    """Test double: records commands, returns canned responses for query()."""

    def __init__(self, canned_responses: dict[str, str] | None = None) -> None:
        self.commands: list[NciCommand] = []
        self.canned_responses: dict[str, str] = canned_responses or {}

    async def send_command(self, cmd: NciCommand) -> None:
        self.commands.append(cmd)

    async def query(self, cmd: NciCommand, timeout: float = 1.0) -> str | None:
        self.commands.append(cmd)
        return self.canned_responses.get(cmd.name)

    def reset(self) -> None:
        self.commands.clear()


# Verify protocol conformance at import time
_: type[NciTransport] = MockNciTransport  # type: ignore[assignment]
