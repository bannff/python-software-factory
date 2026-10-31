"""Real refresh-token -> access-token acquirer + composite HTTP provider.

``HttpRefreshTokenAcquirer`` is the broker's ``TokenAcquirer`` for OAuth
providers: it exchanges the durable refresh token (read from the vault by the
broker) for a short-lived access token at the provider token endpoint. Generic
across OAuth providers — the endpoint/scopes come from the OAuth manifest, keyed
by ``route.provider_id``. ``HttpProvider`` composes it with the SSRF-pinned
egress transport so one object satisfies both broker ports over one client.
Tokens are returned only to the broker (in-memory); never persisted or logged.
"""
from __future__ import annotations

import time
from typing import Any, Mapping

from ..egress_models import ProviderRoute
from ..egress_ports import AcquiredToken
from ..oauth_provider_registry import resolve_oauth_provider
from .http_egress import HttpProviderEgress


class HttpRefreshTokenAcquirer:
    """Exchange a stored refresh token for an access token (OAuth refresh grant)."""

    def __init__(self, client: Any, *, clock: Any = time.time,
                 client_secret: str = "") -> None:
        self._client = client
        self._clock = clock
        self._client_secret = client_secret

    def acquire(self, route: ProviderRoute, secret: Mapping[str, Any], *,
                force_refresh: bool) -> AcquiredToken | None:
        provider = resolve_oauth_provider(route.provider_id)
        refresh = secret.get("refresh_token")
        if provider is None or not provider.configured() \
                or not isinstance(refresh, str) or not refresh:
            return None
        data = {"grant_type": "refresh_token", "refresh_token": refresh,
                "client_id": provider.client_id, "scope": " ".join(provider.scopes)}
        if self._client_secret:
            data["client_secret"] = self._client_secret
        try:
            resp = self._client.post(
                provider.token_url, data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=route.timeout_s, follow_redirects=False)
        except Exception:
            return None
        if int(getattr(resp, "status_code", 0)) != 200:
            return None
        try:
            body = resp.json()
        except Exception:
            return None
        access = body.get("access_token") if isinstance(body, dict) else None
        if not isinstance(access, str) or not access:
            return None
        expires_in = body.get("expires_in") if isinstance(body.get("expires_in"), int) else 3600
        rotated = None
        new_refresh = body.get("refresh_token")
        if isinstance(new_refresh, str) and new_refresh and new_refresh != refresh:
            rotated = {"refresh_token": new_refresh}
        return AcquiredToken(access_token=access,
                             expires_at=self._clock() + expires_in, rotated_secret=rotated)


class HttpProvider:
    """Compose the refresh acquirer + SSRF-pinned egress over one httpx client."""

    def __init__(self, client: Any, *, client_secret: str = "") -> None:
        self._acquirer = HttpRefreshTokenAcquirer(client, client_secret=client_secret)
        self._egress = HttpProviderEgress(client)

    def acquire(self, route: ProviderRoute, secret: Mapping[str, Any], *,
                force_refresh: bool) -> AcquiredToken | None:
        return self._acquirer.acquire(route, secret, force_refresh=force_refresh)

    def call(self, route: ProviderRoute, access_token: str,
             payload: Mapping[str, Any]) -> tuple[str, dict[str, Any]]:
        return self._egress.call(route, access_token, payload)


__all__ = ["HttpProvider", "HttpRefreshTokenAcquirer"]
