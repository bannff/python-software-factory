"""Owner isolation and lifecycle checks for SessionRegistry."""
from __future__ import annotations

import pytest

from factory.terminal.runtime.models import TerminalSpawnSpec
from factory.terminal.runtime.session_registry import (
    SessionRegistry, TerminalSessionUnavailable,
)


@pytest.mark.asyncio
async def test_registry_scopes_session_access_to_owner(tmp_path) -> None:
    registry = SessionRegistry()
    opened = await registry.open(
        "tenant", "alice", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    try:
        with pytest.raises(TerminalSessionUnavailable):
            await registry.write("tenant", "bob", opened.session_id, "echo denied\n")
        assert [item.session_id for item in registry.list("tenant", "alice")] == [opened.session_id]
        assert registry.list("tenant", "bob") == []
    finally:
        await registry.close("tenant", "alice", opened.session_id)


@pytest.mark.asyncio
async def test_disconnect_reconnect_replays_scrollback(tmp_path) -> None:
    registry = SessionRegistry()
    opened = await registry.open(
        "tenant", "owner", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    try:
        await registry.write("tenant", "owner", opened.session_id, "printf 'REPLAY_ME\\n'\n")
        for _ in range(30):
            chunk = await registry.read("tenant", "owner", opened.session_id, 0.1)
            if "REPLAY_ME" in chunk.data:
                break
        _, _, epoch = registry.mark_connected(
            "tenant", "owner", opened.session_id)
        assert registry.mark_disconnected(
            "tenant", "owner", opened.session_id, epoch)
        _, replay, _ = registry.mark_connected(
            "tenant", "owner", opened.session_id)
        assert b"REPLAY_ME" in replay
    finally:
        await registry.close("tenant", "owner", opened.session_id)


@pytest.mark.asyncio
async def test_close_all_terminates_every_session(tmp_path) -> None:
    registry = SessionRegistry()
    first = await registry.open(
        "tenant", "owner", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    second = await registry.open(
        "tenant", "owner", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    assert await registry.close_all() == 2
    assert registry.list("tenant", "owner") == []
    assert first.session_id != second.session_id


@pytest.mark.asyncio
async def test_stale_connection_epoch_cannot_disconnect_or_reap_live_owner(tmp_path) -> None:
    registry = SessionRegistry()
    opened = await registry.open(
        "tenant", "owner", TerminalSpawnSpec(shell="/bin/sh", cwd=str(tmp_path)))
    try:
        _, _, first = registry.mark_connected(
            "tenant", "owner", opened.session_id)
        _, _, second = registry.mark_connected(
            "tenant", "owner", opened.session_id)
        assert second > first
        assert registry.connection_is_current(
            "tenant", "owner", opened.session_id, second)
        assert not registry.mark_disconnected(
            "tenant", "owner", opened.session_id, first)
        assert await registry.reap_orphans(now=10_000_000.0) == 0
        assert registry.list("tenant", "owner")
        assert registry.mark_disconnected(
            "tenant", "owner", opened.session_id, second)
    finally:
        await registry.close("tenant", "owner", opened.session_id)
