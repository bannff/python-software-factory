"""Thin HTTP/WebSocket transport over ``factory.terminal.interface``."""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import logging
import secrets
from typing import Any

from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.websockets import WebSocket

from factory.terminal.interface import TerminalSpawnSpec, get_runtime

from .terminal_socket_owners import claim_socket, close_socket, release_socket
from .terminal_ws_stream import receive_input, send_output

_TICKETS: dict[str, tuple[bytes, str, str]] = {}
_LOGGER = logging.getLogger(__name__)


async def _identity(request: Any) -> tuple[str, str] | None:
    from .bridge import _extract_envelope
    envelope = await _extract_envelope(request)
    if not envelope:
        return None
    return envelope["tenant_id"], envelope["principal_id"]


def _mint(session_id: str, identity: tuple[str, str]) -> str:
    ticket = secrets.token_urlsafe(32)
    _TICKETS[session_id] = (
        hashlib.sha256(ticket.encode()).digest(), identity[0], identity[1])
    return ticket


def prune_terminal_tickets(active_session_ids: frozenset[str]) -> None:
    for session_id in tuple(_TICKETS):
        if session_id not in active_session_ids:
            _TICKETS.pop(session_id, None)


def _ticket(
    websocket: Any, session_id: str,
) -> tuple[str, tuple[str, str]] | None:
    prefix = "terminal."
    offered = websocket.headers.get("sec-websocket-protocol", "")
    values = [value.strip() for value in offered.split(",")]
    token = next((value[len(prefix):] for value in values if value.startswith(prefix)), None)
    stored = _TICKETS.get(session_id)
    if token is None or stored is None:
        return None
    expected, tenant_id, principal_id = stored
    if not hmac.compare_digest(hashlib.sha256(token.encode()).digest(), expected):
        return None
    return prefix + token, (tenant_id, principal_id)


def _ws_url(request: Request, session_id: str) -> str:
    return str(request.url.replace(
        scheme="wss" if request.url.scheme == "https" else "ws",
        path=f"/api/terminal/ws/{session_id}", query="",
    ))


def register_terminal_routes(app: Any) -> None:
    @app.post("/api/terminal/sessions")
    async def open_session(request: Request) -> JSONResponse:
        identity = await _identity(request)
        if identity is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            spec = TerminalSpawnSpec.model_validate(await request.json())
            session = await get_runtime().open_session(*identity, spec)
        except Exception as exc:
            _LOGGER.warning(
                "Terminal session creation failed (%s)", type(exc).__name__, exc_info=True)
            return JSONResponse({"error": "terminal_unavailable"}, status_code=400)
        return JSONResponse({
            "session": session.model_dump(),
            "ticket": _mint(session.session_id, identity),
            "ws_url": _ws_url(request, session.session_id),
        })

    @app.get("/api/terminal/sessions")
    async def list_sessions(request: Request) -> JSONResponse:
        identity = await _identity(request)
        if identity is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        sessions = await get_runtime().list_sessions(*identity)
        return JSONResponse({"sessions": [item.model_dump() for item in sessions]})

    @app.get("/api/terminal/shells")
    async def list_shells(request: Request) -> JSONResponse:
        if await _identity(request) is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        return JSONResponse({"shells": get_runtime().list_shells()})

    @app.post("/api/terminal/sessions/{session_id}/attach")
    async def attach_session(session_id: str, request: Request) -> JSONResponse:
        identity = await _identity(request)
        if identity is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        sessions = await get_runtime().list_sessions(*identity)
        session = next((item for item in sessions if item.session_id == session_id), None)
        if session is None or not session.alive:
            return JSONResponse({"error": "terminal_unavailable"}, status_code=404)
        return JSONResponse({
            "session": session.model_dump(),
            "ticket": _mint(session_id, identity),
            "ws_url": _ws_url(request, session_id),
        })

    @app.delete("/api/terminal/sessions/{session_id}")
    async def close_session(session_id: str, request: Request) -> JSONResponse:
        identity = await _identity(request)
        if identity is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        closed = await get_runtime().close_session(*identity, session_id)
        if closed:
            await close_socket(session_id)
        _TICKETS.pop(session_id, None)
        return JSONResponse({"session_id": session_id, "closed": closed})

    @app.websocket("/api/terminal/ws/{session_id}")
    async def terminal_socket(websocket: WebSocket, session_id: str) -> None:
        authorized = _ticket(websocket, session_id)
        if authorized is None:
            await websocket.close(code=4403)
            return
        protocol, identity = authorized
        runtime = get_runtime()
        try:
            session, replay, epoch = runtime.connect_session(
                *identity, session_id)
        except Exception:
            await websocket.close(code=4404)
            return
        await websocket.accept(subprotocol=protocol)
        await claim_socket(session_id, epoch, websocket)
        await websocket.send_json({"type": "ready", "shell": session.shell,
                                   "cols": session.cols, "rows": session.rows})
        if replay:
            await websocket.send_bytes(replay)
        sender = asyncio.create_task(send_output(
            websocket, runtime, session, identity, epoch))
        try:
            await receive_input(websocket, runtime, session, identity, epoch)
        finally:
            sender.cancel()
            await asyncio.gather(sender, return_exceptions=True)
            if await release_socket(session_id, epoch, websocket):
                runtime.disconnect_session(*identity, session_id, epoch)


__all__ = ["prune_terminal_tickets", "register_terminal_routes"]
