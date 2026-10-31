"""Terminal WebSocket byte and control-frame pumps."""
from __future__ import annotations

import json
from typing import Any

from factory.terminal.runtime.models import TerminalResizeSpec


async def send_output(
    websocket: Any, runtime: Any, session: Any,
    identity: tuple[str, str], epoch: int,
) -> None:
    while runtime.connection_is_current(*identity, session.session_id, epoch):
        data, alive = await runtime.read_bytes(
            *identity, session.session_id, 0.25)
        if data and runtime.connection_is_current(
            *identity, session.session_id, epoch,
        ):
            await websocket.send_bytes(data)
        if not alive:
            await websocket.send_json({"type": "exit"})
            await websocket.close(code=1000)
            return


async def receive_input(
    websocket: Any, runtime: Any, session: Any,
    identity: tuple[str, str], epoch: int,
) -> None:
    while runtime.connection_is_current(*identity, session.session_id, epoch):
        message = await websocket.receive()
        if message.get("type") == "websocket.disconnect":
            return
        if message.get("bytes") is not None:
            await runtime.write_bytes(
                *identity, session.session_id, message["bytes"])
        elif message.get("text") is not None:
            await _control(runtime, session, identity, message["text"], websocket)


async def _control(
    runtime: Any, session: Any, identity: tuple[str, str],
    raw: str, websocket: Any,
) -> None:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError:
        return
    if value.get("type") == "resize":
        resized = TerminalResizeSpec.model_validate({
            "session_id": session.session_id,
            "cols": value.get("cols"), "rows": value.get("rows"),
        })
        await runtime.resize(
            *identity, session.session_id, resized.cols, resized.rows)
    elif value.get("type") == "ping":
        await websocket.send_json({"type": "pong"})


__all__ = ["receive_input", "send_output"]
