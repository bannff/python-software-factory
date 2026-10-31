"""Authenticated HTTP transport for Terminal completion."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError
from starlette.requests import Request
from starlette.responses import JSONResponse

from factory.terminal.interface import TerminalCompletionSpec, get_runtime

from .terminal_ws_routes import _identity


def register_terminal_completion_routes(app: Any) -> None:
    @app.post("/api/terminal/sessions/{session_id}/complete")
    async def complete(session_id: str, request: Request) -> JSONResponse:
        identity = await _identity(request)
        if identity is None:
            return JSONResponse({"error": "unauthorized"}, status_code=401)
        try:
            body = await request.json()
            spec = TerminalCompletionSpec.model_validate({
                **body, "session_id": session_id,
            })
        except (TypeError, ValueError, ValidationError):
            return JSONResponse(
                {"error": "terminal_completion_invalid"}, status_code=400)
        try:
            result = await get_runtime().complete(*identity, spec)
        except ValueError:
            return JSONResponse(
                {"error": "terminal_unavailable"}, status_code=404)
        return JSONResponse(result.model_dump())


__all__ = ["register_terminal_completion_routes"]
