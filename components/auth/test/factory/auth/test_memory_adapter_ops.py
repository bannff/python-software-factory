"""Tests for memory adapter token operations (refresh, revoke, exchange, userinfo)."""
from __future__ import annotations

from factory.auth.runtime.adapters import MemoryBackend
from factory.auth.runtime.envelope import parse_envelope


class TestMemoryBackendRefreshToken:
    """Tests for token refresh."""

    def test_refresh_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", scopes=["read"])
        _, refresh = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.refresh_token(refresh, envelope=env)

        assert result["ok"] is True
        assert "access_token" in result
        assert "refresh_token" in result
        assert result["token_type"] == "Bearer"

    def test_refresh_invalid_token(self) -> None:
        backend = MemoryBackend()
        env = parse_envelope(None)
        result = backend.refresh_token("invalid-refresh", envelope=env)
        assert result["ok"] is False
        assert result["error"] == "invalid_refresh_token"


class TestMemoryBackendRevokeToken:
    """Tests for token revocation."""

    def test_revoke_access_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser")
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.revoke_token(token, envelope=env)
        assert result["ok"] is True
        assert result["revoked"] is True

        verify = backend.verify_access_token(token, required_audience=None, required_scopes=None, envelope=env)
        assert verify["ok"] is False
        assert verify["error"] == "token_revoked"

    def test_revoke_refresh_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser")
        token, refresh = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.revoke_token(refresh, envelope=env)
        assert result["ok"] is True

        verify = backend.verify_access_token(token, required_audience=None, required_scopes=None, envelope=env)
        assert verify["ok"] is False


class TestMemoryBackendExchangeToken:
    """Tests for token exchange."""

    def test_exchange_token(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", scopes=["read", "write"])
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.exchange_token(
            token,
            subject_token_type="urn:ietf:params:oauth:token-type:access_token",
            scope="read",
            envelope=env,
        )

        assert result["ok"] is True
        assert "access_token" in result
        assert result["scope"] == "read"


class TestMemoryBackendUserInfo:
    """Tests for user info retrieval."""

    def test_get_user_info(self) -> None:
        backend = MemoryBackend()
        backend.add_user("user-1", "testuser", email="test@example.com")
        token, _ = backend.create_token("user-1")

        env = parse_envelope(None)
        result = backend.get_user_info(token, envelope=env)

        assert result["ok"] is True
        assert result["user_info"]["sub"] == "user-1"
        assert result["user_info"]["preferred_username"] == "testuser"
        assert result["user_info"]["email"] == "test@example.com"

    def test_get_user_info_invalid_token(self) -> None:
        backend = MemoryBackend()
        env = parse_envelope(None)
        result = backend.get_user_info("invalid-token", envelope=env)
        assert result["ok"] is False
        assert result["error"] == "invalid_token"
