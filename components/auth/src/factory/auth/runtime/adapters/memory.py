"""In-memory mock authentication backend for testing.

This adapter stores users and tokens in memory, providing deterministic
behavior for tests without requiring an external Keycloak server.
"""
from __future__ import annotations

import hashlib
import secrets
import time
from typing import Any

from factory.auth.runtime.envelope import Envelope
from factory.auth.runtime.models import Principal
from .memory_models import StoredUser, StoredToken
from .memory_ops import MemoryTokenOps


class MemoryBackend(MemoryTokenOps):
    """In-memory authentication backend for testing.

    Implements the AuthBackend protocol with in-memory storage.
    Useful for unit tests and development without Keycloak.
    """
    kind = "memory"

    def __init__(self) -> None:
        self._users: dict[str, StoredUser] = {}
        self._tokens: dict[str, StoredToken] = {}
        self._refresh_tokens: dict[str, str] = {}
        self._default_ttl = 3600

    def add_user(
        self,
        subject: str,
        username: str,
        *,
        email: str | None = None,
        tenant_id: str | None = None,
        scopes: list[str] | None = None,
        roles: list[str] | None = None,
    ) -> StoredUser:
        """Add a user to the in-memory store (test helper)."""
        user = StoredUser(
            subject=subject, username=username, email=email,
            tenant_id=tenant_id, scopes=scopes or [], roles=roles or [],
        )
        self._users[subject] = user
        return user

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
        if subject not in self._users:
            raise ValueError(f"User {subject} not found")

        token = self._generate_token()
        refresh = self._generate_token() if with_refresh else None
        expires_at = time.time() + (ttl or self._default_ttl)

        stored = StoredToken(
            token=token, subject=subject, expires_at=expires_at,
            scopes=scopes or self._users[subject].scopes,
            audience=audience, refresh_token=refresh,
        )
        self._tokens[token] = stored
        if refresh:
            self._refresh_tokens[refresh] = token

        return token, refresh

    def seed_token(
        self, token: str, subject: str, *, audience: str | None = None,
        ttl: int = 3600,
    ) -> None:
        """Install one operator-supplied opaque token for explicit local mode."""
        if subject not in self._users:
            raise ValueError("seed subject not found")
        if not 16 <= len(token) <= 512 or ttl < 1 or ttl > 86400:
            raise ValueError("invalid local token seed")
        self._tokens[token] = StoredToken(
            token=token, subject=subject, expires_at=time.time() + ttl,
            scopes=self._users[subject].scopes, audience=audience,
            refresh_token=None,
        )

    def _generate_token(self) -> str:
        """Generate a random token string."""
        return hashlib.sha256(secrets.token_bytes(32)).hexdigest()

    def health_check(self) -> dict[str, Any]:
        """Check backend health (always healthy for memory backend)."""
        return {
            "attempted": True, "ok": True, "backend": "memory",
            "users_count": len(self._users), "tokens_count": len(self._tokens),
        }

    def verify_access_token(
        self,
        token: str,
        *,
        required_audience: str | None,
        required_scopes: list[str] | None,
        envelope: Envelope,
    ) -> dict[str, Any]:
        """Verify an access token and extract claims."""
        stored = self._tokens.get(token)
        if not stored:
            return {"ok": False, "error": "invalid_token"}
        if stored.revoked:
            return {"ok": False, "error": "token_revoked"}
        if time.time() > stored.expires_at:
            return {"ok": False, "error": "expired"}
        if required_audience and stored.audience != required_audience:
            return {"ok": False, "error": "audience_mismatch"}
        if required_scopes:
            missing = sorted(set(required_scopes) - set(stored.scopes))
            if missing:
                return {"ok": False, "error": "missing_scopes", "missing": missing}

        user = self._users.get(stored.subject)
        if not user:
            return {"ok": False, "error": "user_not_found"}
        if envelope.tenant_id and user.tenant_id and envelope.tenant_id != user.tenant_id:
            return {"ok": False, "error": "tenant_mismatch"}

        principal = Principal(
            subject=user.subject, tenant_id=user.tenant_id or envelope.tenant_id,
            username=user.username, email=user.email, scopes=stored.scopes, roles=user.roles,
        )
        claims = {
            "sub": user.subject, "preferred_username": user.username,
            "email": user.email, "scope": " ".join(stored.scopes), "exp": int(stored.expires_at),
        }
        if user.tenant_id:
            claims["tenant_id"] = user.tenant_id

        return {"ok": True, "principal": principal.model_dump(), "claims": claims}

    def introspect_token(self, token: str, *, envelope: Envelope) -> dict[str, Any]:
        """Introspect a token to check if it's active."""
        stored = self._tokens.get(token)
        if not stored or stored.revoked or time.time() > stored.expires_at:
            return {"active": False, "error": "invalid_or_expired"}

        user = self._users.get(stored.subject)
        tenant_id = user.tenant_id if user else None

        return {
            "active": True, "exp": int(stored.expires_at),
            "sub": stored.subject, "tenant_id": tenant_id or envelope.tenant_id,
        }

    def resolve_principal(self, *, envelope: Envelope) -> dict[str, Any]:
        """Resolve principal from envelope context."""
        if envelope.principal_id:
            user = self._users.get(envelope.principal_id)
            if user:
                return {
                    "ok": True,
                    "principal": {
                        "subject": user.subject, "tenant_id": user.tenant_id or envelope.tenant_id,
                        "username": user.username, "email": user.email,
                        "scopes": user.scopes, "roles": user.roles,
                    },
                    "source": "memory",
                }
            return {
                "ok": True,
                "principal": {
                    "subject": envelope.principal_id, "tenant_id": envelope.tenant_id,
                    "username": None, "email": None, "scopes": [], "roles": [],
                },
                "source": "envelope",
            }
        return {"ok": True, "principal": None, "source": "unknown"}
