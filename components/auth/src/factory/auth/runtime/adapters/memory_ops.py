"""Token operations for the in-memory authentication backend.

This module contains the token-related operations (refresh, revoke, exchange, userinfo)
for the MemoryBackend, split out to keep files under 200 LOC.
"""
from __future__ import annotations

import time
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from factory.auth.runtime.envelope import Envelope
    from .memory_models import StoredToken, StoredUser


class MemoryTokenOps:
    """Token operations mixin for MemoryBackend."""

    _users: dict[str, "StoredUser"]
    _tokens: dict[str, "StoredToken"]
    _refresh_tokens: dict[str, str]
    _default_ttl: int

    def create_token(
        self,
        subject: str,
        *,
        scopes: list[str] | None = None,
        audience: str | None = None,
        ttl: int | None = None,
        with_refresh: bool = True,
    ) -> tuple[str, str | None]:
        """Create a token for a user. Returns (access_token, refresh_token)."""
        raise NotImplementedError("Must be implemented by subclass")

    def refresh_token(
        self,
        refresh_token: str,
        *,
        scope: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Exchange a refresh token for a new access token."""
        access_token = self._refresh_tokens.get(refresh_token)
        if not access_token:
            return {"ok": False, "error": "invalid_refresh_token"}

        old_stored = self._tokens.get(access_token)
        if not old_stored:
            return {"ok": False, "error": "invalid_refresh_token"}

        new_scopes = scope.split() if scope else old_stored.scopes
        new_token, new_refresh = self.create_token(
            old_stored.subject,
            scopes=new_scopes,
            audience=old_stored.audience,
        )

        old_stored.revoked = True
        del self._refresh_tokens[refresh_token]

        return {
            "ok": True,
            "access_token": new_token,
            "refresh_token": new_refresh,
            "token_type": "Bearer",
            "expires_in": self._default_ttl,
            "scope": " ".join(new_scopes),
        }

    def revoke_token(
        self,
        token: str,
        *,
        token_type_hint: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Revoke an access or refresh token."""
        if token in self._refresh_tokens:
            access_token = self._refresh_tokens.pop(token)
            if access_token in self._tokens:
                self._tokens[access_token].revoked = True
            return {"ok": True, "revoked": True}

        if token in self._tokens:
            stored = self._tokens[token]
            stored.revoked = True
            if stored.refresh_token and stored.refresh_token in self._refresh_tokens:
                del self._refresh_tokens[stored.refresh_token]
            return {"ok": True, "revoked": True}

        return {"ok": True, "revoked": True}

    def get_user_info(self, access_token: str, *, envelope: "Envelope") -> dict[str, Any]:
        """Get user info from the access token."""
        stored = self._tokens.get(access_token)
        if not stored or stored.revoked or time.time() > stored.expires_at:
            return {"ok": False, "error": "invalid_token"}

        user = self._users.get(stored.subject)
        if not user:
            return {"ok": False, "error": "user_not_found"}

        return {
            "ok": True,
            "user_info": {
                "sub": user.subject,
                "preferred_username": user.username,
                "email": user.email,
                "email_verified": user.email is not None,
            },
        }

    def exchange_token(
        self,
        subject_token: str,
        *,
        subject_token_type: str,
        requested_token_type: str | None = None,
        audience: str | None = None,
        scope: str | None = None,
        envelope: "Envelope",
    ) -> dict[str, Any]:
        """Exchange one token for another."""
        stored = self._tokens.get(subject_token)
        if not stored or stored.revoked or time.time() > stored.expires_at:
            return {"ok": False, "error": "invalid_subject_token"}

        new_scopes = scope.split() if scope else stored.scopes
        new_token, _ = self.create_token(
            stored.subject,
            scopes=new_scopes,
            audience=audience or stored.audience,
            with_refresh=False,
        )

        return {
            "ok": True,
            "access_token": new_token,
            "token_type": "Bearer",
            "expires_in": self._default_ttl,
            "scope": " ".join(new_scopes),
            "issued_token_type": requested_token_type or "urn:ietf:params:oauth:token-type:access_token",
        }
