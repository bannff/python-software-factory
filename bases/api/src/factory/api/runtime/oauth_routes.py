"""OAuth callback route — a dumb transport forwarder (no token ever seen here).

The provider redirects the user's browser to GET /oauth/callback?code=&state=.
This handler forwards state+code to the auth brick's public
``auth.oauth_enroll_complete`` tool and renders a plain confirmation page. It
holds no identity of its own: the principal is re-derived server-side from the
single-use ``state`` (minted under the authenticated envelope at begin-time), so
this endpoint needs no bearer/session. It never handles a token or secret — the
tool returns only {status, generation}.
"""
from __future__ import annotations

from typing import Any


def register_oauth_routes(app: Any) -> None:
    from starlette.requests import Request
    from starlette.responses import HTMLResponse

    from .bridge import _call_tool

    def _page(title: str, message: str, ok: bool) -> HTMLResponse:
        color = "#16a34a" if ok else "#dc2626"
        html = (
            f"<!doctype html><html><head><meta charset='utf-8'>"
            f"<title>{title}</title></head>"
            f"<body style='font-family:system-ui;max-width:32rem;margin:4rem auto;text-align:center'>"
            f"<h2 style='color:{color}'>{title}</h2><p>{message}</p>"
            f"<p style='color:#6b7280'>You can close this window.</p></body></html>"
        )
        return HTMLResponse(html, status_code=200 if ok else 400)

    async def oauth_callback(request: Request) -> HTMLResponse:
        params = request.query_params
        if params.get("error"):
            return _page("Connection cancelled", "The provider denied the request.", False)
        code, state = params.get("code"), params.get("state")
        if not code or not state:
            return _page("Connection failed", "Missing authorization code or state.", False)
        result = await _call_tool("auth.oauth_enroll_complete", {"state": state, "code": code})
        ok = isinstance(result, dict) and result.get("ok") is True
        if ok:
            return _page("Connected", "Your account is now connected.", True)
        return _page("Connection failed", "Could not complete the connection.", False)

    from starlette.routing import Route
    app.routes.append(Route("/oauth/callback", oauth_callback, methods=["GET"]))


__all__ = ["register_oauth_routes"]
