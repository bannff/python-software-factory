"""Streamable-HTTP ASGI projection for the native MCP-v2 server."""

from __future__ import annotations

from typing import Any


def build_streamable_http_app(
    server: Any, *, path: str = "/", auth: Any | None = None,
    token_verifier: Any | None = None, host: str = "127.0.0.1",
) -> Any:
    """Build the SDK-owned HTTP app with native bearer enforcement."""
    from starlette.middleware.cors import CORSMiddleware

    from factory.mcp_utils.interface import cors_options

    from .transport_security_config import resolve_transport_security

    app = server.streamable_http_app(
        streamable_http_path=path,
        stateless_http=True,
        auth=auth,
        token_verifier=token_verifier,
        host=host,
        transport_security=resolve_transport_security(),
    )
    app.add_middleware(CORSMiddleware, **cors_options())
    return app


__all__ = ["build_streamable_http_app"]
