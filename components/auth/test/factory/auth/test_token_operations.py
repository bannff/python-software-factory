"""Tests for token refresh and revocation operations.

See also:
- test_token_userinfo.py - User info and token exchange tests
"""
from __future__ import annotations

import httpx

from factory.auth.runtime.envelope import parse_envelope
from factory.auth.runtime.keycloak import KeycloakBackend
from factory.auth.runtime.models import KeycloakBackendConfig


def _make_keycloak_backend(handler) -> KeycloakBackend:
    """Create a KeycloakBackend with mocked HTTP."""
    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
    cfg = KeycloakBackendConfig(
        schema_version=1,
        kind="keycloak",
        base_url="http://kc",
        realm="testrealm",
        issuer="http://kc/realms/testrealm",
        jwks_url="http://kc/jwks",
        client_id="test-client",
        client_secret="test-secret",
    )
    return KeycloakBackend(cfg, http=client)


class TestRefreshToken:
    """Tests for token refresh functionality."""

    def test_refresh_token_success(self) -> None:
        """Valid refresh token should return new access token."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "new-access-token",
                        "refresh_token": "new-refresh-token",
                        "token_type": "Bearer",
                        "expires_in": 300,
                    },
                )
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.refresh_token(
            refresh_token="valid-refresh-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is True
        assert result["access_token"] == "new-access-token"
        assert result["refresh_token"] == "new-refresh-token"
        assert result["expires_in"] == 300

    def test_refresh_token_expired(self) -> None:
        """Expired refresh token should return error."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                return httpx.Response(
                    400,
                    json={
                        "error": "invalid_grant",
                        "error_description": "Token is not active",
                    },
                )
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.refresh_token(
            refresh_token="expired-refresh-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result

    def test_refresh_token_network_error(self) -> None:
        """Network error during refresh should return error."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.refresh_token(
            refresh_token="valid-refresh-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result


class TestRevokeToken:
    """Tests for token revocation functionality."""

    def test_revoke_token_success(self) -> None:
        """Valid token revocation should succeed."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "revoke" in str(request.url):
                return httpx.Response(200)  # Keycloak returns 200 on success
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.revoke_token(
            token="valid-token",
            token_type_hint="access_token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is True
        assert result["revoked"] is True

    def test_revoke_refresh_token(self) -> None:
        """Refresh token revocation should succeed."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "revoke" in str(request.url):
                return httpx.Response(200)
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.revoke_token(
            token="valid-refresh-token",
            token_type_hint="refresh_token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is True
        assert result["revoked"] is True

    def test_revoke_token_error(self) -> None:
        """Revocation error should be handled gracefully."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "revoke" in str(request.url):
                return httpx.Response(400, json={"error": "invalid_token"})
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.revoke_token(
            token="invalid-token",
            token_type_hint="access_token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result
