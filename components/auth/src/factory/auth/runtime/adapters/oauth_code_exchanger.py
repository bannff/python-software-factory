"""Authorization-code -> refresh-token exchange (enrollment half).

POSTs the one-time authorization code + PKCE verifier to the provider token
endpoint and returns the durable refresh token. httpx client injected so it is
offline-testable with a MockTransport. Never logs the code, verifier, or token.
"""
from __future__ import annotations

from typing import Any

from ..oauth_provider_registry import OAuthProvider


class OAuthCodeExchangeError(ValueError):
    """Opaque failure for a rejected or malformed code exchange."""


class OAuthCodeExchanger:
    """Exchange one authorization code for a durable refresh token."""

    def __init__(self, client: Any) -> None:
        self._client = client  # httpx.Client (or MockTransport-backed)

    def exchange(self, provider: OAuthProvider, *, code: str, code_verifier: str,
                 redirect_uri: str, client_secret: str = "") -> dict[str, str]:
        data = {
            "grant_type": "authorization_code", "code": code,
            "redirect_uri": redirect_uri, "client_id": provider.client_id,
            "code_verifier": code_verifier, "scope": " ".join(provider.scopes),
        }
        if client_secret:
            data["client_secret"] = client_secret
        try:
            resp = self._client.post(
                provider.token_url, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=10, follow_redirects=False)
        except Exception as exc:
            raise OAuthCodeExchangeError("code exchange failed") from exc
        if int(getattr(resp, "status_code", 0)) != 200:
            raise OAuthCodeExchangeError("code exchange rejected")
        try:
            body = resp.json()
        except Exception as exc:
            raise OAuthCodeExchangeError("code exchange malformed") from exc
        refresh = body.get("refresh_token") if isinstance(body, dict) else None
        if not isinstance(refresh, str) or not refresh:
            raise OAuthCodeExchangeError("no refresh token issued")
        return {"refresh_token": refresh}


__all__ = ["OAuthCodeExchangeError", "OAuthCodeExchanger"]
