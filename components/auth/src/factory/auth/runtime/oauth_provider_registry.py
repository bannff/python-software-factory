"""Immutable OAuth provider manifests — the authorization-code handshake half.

Distinct from ``egress_registry`` (which holds egress origins/routes): this holds
the OAuth authorize/token endpoints, the fixed redirect-URI allowlist, scopes,
and the ``client_id`` (from the one-time app registration, supplied via env).
The real Microsoft/Google endpoints are public knowledge and seeded here; only
the ``client_id`` (and, for confidential clients, a secret) come from config, so
flipping to a real connection is a config change, not a code change.
"""
from __future__ import annotations

import os
from dataclasses import dataclass

_PROVIDERS: dict[str, "OAuthProvider"] = {}


def _valid_redirect(url: str) -> bool:
    return url.startswith("https://") or url.startswith("http://localhost") \
        or url.startswith("http://127.0.0.1")


@dataclass(frozen=True, slots=True)
class OAuthProvider:
    provider_id: str
    authorize_url: str
    token_url: str
    scopes: tuple[str, ...]
    redirect_uris: frozenset[str]
    secret_slot_kind: str = "refresh_token"
    client_id: str = ""

    def __post_init__(self) -> None:
        for url in (self.authorize_url, self.token_url):
            if not url.startswith("https://"):
                raise ValueError("OAuth endpoints must be https")
        if not self.redirect_uris or not all(_valid_redirect(u) for u in self.redirect_uris):
            raise ValueError("redirect_uris must be https or loopback")

    def default_redirect(self) -> str:
        return sorted(self.redirect_uris)[0]

    def configured(self) -> bool:
        return bool(self.client_id)


def register_oauth_provider(provider: OAuthProvider) -> None:
    existing = _PROVIDERS.get(provider.provider_id)
    if existing is not None and existing != provider:
        raise ValueError("oauth provider already registered with different manifest")
    _PROVIDERS[provider.provider_id] = provider


def resolve_oauth_provider(provider_id: str) -> OAuthProvider | None:
    return _PROVIDERS.get(provider_id)


def _redirect() -> str:
    return os.environ.get("OAUTH_REDIRECT_URI", "http://localhost:8000/oauth/callback")


def _seed_defaults() -> None:
    redirect = frozenset({_redirect()})
    register_oauth_provider(OAuthProvider(
        provider_id="microsoft",
        authorize_url="https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        token_url="https://login.microsoftonline.com/common/oauth2/v2.0/token",
        scopes=("offline_access", "Mail.Send", "Mail.Read"),
        redirect_uris=redirect,
        client_id=os.environ.get("MS_OAUTH_CLIENT_ID", "")))
    register_oauth_provider(OAuthProvider(
        provider_id="google",
        authorize_url="https://accounts.google.com/o/oauth2/v2/auth",
        token_url="https://oauth2.googleapis.com/token",
        scopes=("https://www.googleapis.com/auth/gmail.send",
                "https://www.googleapis.com/auth/gmail.readonly"),
        redirect_uris=redirect,
        client_id=os.environ.get("GOOGLE_OAUTH_CLIENT_ID", "")))


_seed_defaults()


__all__ = ["OAuthProvider", "register_oauth_provider", "resolve_oauth_provider"]
