"""Cross-origin policy for the Companion-X HTTP surface (single source).

Both composition roots share this:
- the ``api`` base mounts the MCP Streamable-HTTP app under a FastAPI parent
  (``RESTAdapter`` → ``add_middleware(CORSMiddleware, **cors_options())``);
- the ``mcp_server`` base is FastMCP-rooted (``http_app(middleware=[cors_middleware()])``).

This replaces the per-route hand-rolled ``_CORS_HEADERS`` that previously left
the mounted ``/mcp`` app with no CORS at all — browser clients (the Next
dashboard at :3000) were blocked from the MCP handshake.
Framework-first: Starlette's ``CORSMiddleware`` is the primitive; origins are
data (env-overridable), never hardcoded policy in a base.

Design (meta-architect verdict 97acf12c, bd:python-factory-iqm3h):
- Explicit allowlist, NOT ``*`` (a wildcard + a route that also sets ``*``
  leaks ``*`` to disallowed origins; and ``allow_credentials`` can never pair
  with ``*``).
- ``allow_credentials=False`` — MCP carries a session id in a header, not a
  cookie.
- ``expose_headers`` MUST include ``mcp-session-id`` so the browser client can
  read it off the initialize response and echo it on later requests; without
  it the MCP session silently breaks even once ACAO is correct.
"""

from __future__ import annotations

import os

_DEFAULT_ORIGINS = "http://localhost:3000"

_ALLOW_METHODS = ["GET", "POST", "DELETE", "OPTIONS"]
# Request headers a browser MCP/SSE client sends: JSON body + the MCP session/
# protocol headers + SSE reconnect + auth (Phase 2).
_ALLOW_HEADERS = [
    "content-type",
    "mcp-session-id",
    "mcp-protocol-version",
    "last-event-id",
    "accept",
    "authorization",
]
# Response headers the browser must be allowed to READ off the response.
_EXPOSE_HEADERS = ["mcp-session-id", "mcp-protocol-version"]


def cors_origins() -> list[str]:
    """Allowed origins from ``COMPANION_X_CORS_ORIGINS`` (comma-separated)."""
    raw = os.environ.get("COMPANION_X_CORS_ORIGINS", _DEFAULT_ORIGINS)
    return [o.strip() for o in raw.split(",") if o.strip()]


def cors_options() -> dict:
    """Keyword args for Starlette ``CORSMiddleware`` / FastAPI ``add_middleware``."""
    return {
        "allow_origins": cors_origins(),
        "allow_credentials": False,
        "allow_methods": _ALLOW_METHODS,
        "allow_headers": _ALLOW_HEADERS,
        "expose_headers": _EXPOSE_HEADERS,
    }
