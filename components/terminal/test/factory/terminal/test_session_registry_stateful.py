"""Hypothesis state-machine coverage for terminal registry ownership/lifecycle."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from hypothesis import settings
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

import factory.terminal.runtime.session_registry as registry_module
from factory.terminal.runtime.models import TerminalSpawnSpec
from factory.terminal.runtime.session_registry import MAX_SESSIONS, SessionRegistry


@dataclass
class FakeSession:
    session_id: str
    tenant_id: str
    principal_id: str
    shell: str
    cwd: str
    cols: int
    rows: int
    alive: bool = True
    disconnected_at: float | None = None
    _scrollback: bytearray = field(default_factory=bytearray)

    async def write(self, data: bytes) -> None:
        self._scrollback.extend(data)

    async def read(self, timeout: float) -> bytes:
        return b""

    def resize(self, cols: int, rows: int) -> None:
        self.cols, self.rows = cols, rows

    def scrollback(self) -> bytes:
        return bytes(self._scrollback)

    async def close(self) -> None:
        self.alive = False


async def fake_spawn(
    session_id: str, tenant_id: str, principal_id: str, shell: str,
    cwd: str, cols: int, rows: int,
) -> FakeSession:
    return FakeSession(session_id, tenant_id, principal_id, shell, cwd, cols, rows)


@settings(max_examples=30, stateful_step_count=25, deadline=None)
class RegistryMachine(RuleBasedStateMachine):
    def __init__(self) -> None:
        super().__init__()
        self.registry = SessionRegistry()
        self.expected: dict[str, str] = {}
        self.original = registry_module.spawn_pty
        registry_module.spawn_pty = fake_spawn

    @precondition(lambda self: sum(
        owner == "alice" for owner in self.expected.values()) < MAX_SESSIONS)
    @rule()
    def open_alice(self) -> None:
        self._open("alice")

    @precondition(lambda self: sum(
        owner == "bob" for owner in self.expected.values()) < MAX_SESSIONS)
    @rule()
    def open_bob(self) -> None:
        self._open("bob")

    @precondition(lambda self: bool(self.expected))
    @rule()
    def close_one(self) -> None:
        session_id, owner = next(iter(self.expected.items()))
        assert asyncio.run(self.registry.close("tenant", owner, session_id))
        self.expected.pop(session_id)

    @invariant()
    def owner_lists_match_model(self) -> None:
        for owner in ("alice", "bob"):
            wanted = {sid for sid, value in self.expected.items() if value == owner}
            assert len(wanted) <= MAX_SESSIONS
            actual = {item.session_id for item in self.registry.list("tenant", owner)}
            assert actual == wanted

    def _open(self, owner: str) -> None:
        ref = asyncio.run(self.registry.open(
            "tenant", owner,
            TerminalSpawnSpec(shell="/bin/sh", cwd="/tmp"),
        ))
        self.expected[ref.session_id] = owner

    def teardown(self) -> None:
        for session_id, owner in list(self.expected.items()):
            asyncio.run(self.registry.close("tenant", owner, session_id))
        registry_module.spawn_pty = self.original


TestRegistryStateful = RegistryMachine.TestCase
