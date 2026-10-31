"""Real POSIX PTY lifecycle proof."""
from __future__ import annotations

import asyncio

import pytest

from factory.terminal.runtime.pty_session import spawn_pty
from factory.terminal.runtime.shell_resolver import resolve_shell


@pytest.mark.asyncio
async def test_spawn_write_read_resize_and_close(tmp_path) -> None:
    session = await spawn_pty(
        "term_" + "a" * 32, "tenant", "owner", resolve_shell("/bin/sh"),
        str(tmp_path), 80, 24,
    )
    try:
        session.resize(120, 40)
        assert (session.cols, session.rows) == (120, 40)
        await session.write(b"printf 'PTY_OK\\n'; exit\n")
        output = bytearray()
        for _ in range(40):
            output.extend(await session.read(timeout=0.1))
            if b"PTY_OK" in output:
                break
            await asyncio.sleep(0.01)
        assert b"PTY_OK" in output
    finally:
        await session.close()
    assert session.alive is False


@pytest.mark.asyncio
async def test_scrollback_is_bounded(tmp_path) -> None:
    session = await spawn_pty(
        "term_" + "b" * 32, "tenant", "owner", resolve_shell("/bin/sh"),
        str(tmp_path), 80, 24,
    )
    try:
        await session.write(b"python3 -c \"print('X'*60000)\"\n")
        for _ in range(100):
            await session.read(timeout=0.05)
            if len(session.scrollback()) >= 50 * 1024:
                break
        assert len(session.scrollback()) <= 50 * 1024
    finally:
        await session.close()
