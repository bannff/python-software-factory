"""Single-live-WebSocket ownership for Terminal PTY sessions."""
from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Any


@dataclass(slots=True)
class SocketOwner:
    epoch: int
    socket: Any


_OWNERS: dict[str, SocketOwner] = {}
_LOCK = Lock()


async def claim_socket(session_id: str, epoch: int, socket: Any) -> None:
    with _LOCK:
        previous = _OWNERS.get(session_id)
        _OWNERS[session_id] = SocketOwner(epoch, socket)
    if previous is None or previous.socket is socket:
        return
    try:
        await previous.socket.send_json({"type": "error", "code": "displaced"})
    except Exception:
        pass
    try:
        await previous.socket.close(code=4409)
    except Exception:
        pass


async def release_socket(session_id: str, epoch: int, socket: Any) -> bool:
    """Release only the current owner; displaced cleanup is a no-op."""
    with _LOCK:
        current = _OWNERS.get(session_id)
        if current is None or current.epoch != epoch or current.socket is not socket:
            return False
        _OWNERS.pop(session_id, None)
        return True


async def close_socket(session_id: str) -> None:
    with _LOCK:
        current = _OWNERS.pop(session_id, None)
    if current is not None:
        try:
            await current.socket.close(code=1000)
        except Exception:
            pass


async def close_sockets_not_in(active_session_ids: frozenset[str]) -> None:
    with _LOCK:
        stale = [
            _OWNERS.pop(session_id) for session_id in tuple(_OWNERS)
            if session_id not in active_session_ids
        ]
    for owner in stale:
        try:
            await owner.socket.close(code=1000)
        except Exception:
            pass


async def close_all_sockets() -> None:
    await close_sockets_not_in(frozenset())


def reset_socket_owners() -> None:
    _OWNERS.clear()


__all__ = [
    "claim_socket", "close_all_sockets", "close_socket", "close_sockets_not_in",
    "release_socket", "reset_socket_owners",
]
