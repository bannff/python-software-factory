"""Tests for user info retrieval and token exchange."""
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


class TestGetUserInfo:
    """Tests for user info retrieval."""

    def test_get_user_info_success(self) -> None:
        """Valid access token should return user info."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "userinfo" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "sub": "user-123",
                        "preferred_username": "testuser",
                        "email": "test@example.com",
                        "email_verified": True,
                        "name": "Test User",
                    },
                )
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.get_user_info(
            access_token="valid-access-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is True
        assert result["user_info"]["sub"] == "user-123"
        assert result["user_info"]["preferred_username"] == "testuser"
        assert result["user_info"]["email"] == "test@example.com"

    def test_get_user_info_invalid_token(self) -> None:
        """Invalid access token should return error."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "userinfo" in str(request.url):
                return httpx.Response(401, json={"error": "invalid_token"})
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.get_user_info(
            access_token="invalid-access-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result

    def test_get_user_info_network_error(self) -> None:
        """Network error should return error."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "userinfo" in str(request.url):
                raise httpx.ConnectError("Connection refused")
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.get_user_info(
            access_token="valid-access-token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result


class TestTokenExchange:
    """Tests for token exchange functionality."""

    def test_token_exchange_success(self) -> None:
        """Token exchange should return new token."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                return httpx.Response(
                    200,
                    json={
                        "access_token": "exchanged-token",
                        "token_type": "Bearer",
                        "expires_in": 300,
                    },
                )
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.exchange_token(
            subject_token="original-token",
            subject_token_type="urn:ietf:params:oauth:token-type:access_token",
            requested_token_type="urn:ietf:params:oauth:token-type:access_token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is True
        assert result["access_token"] == "exchanged-token"

    def test_token_exchange_unauthorized(self) -> None:
        """Unauthorized exchange should return error."""

        def handler(request: httpx.Request) -> httpx.Response:
            if "token" in str(request.url):
                return httpx.Response(
                    403,
                    json={
                        "error": "access_denied",
                        "error_description": "Client not allowed to exchange",
                    },
                )
            return httpx.Response(200, json={"keys": []})

        backend = _make_keycloak_backend(handler)
        result = backend.exchange_token(
            subject_token="original-token",
            subject_token_type="urn:ietf:params:oauth:token-type:access_token",
            requested_token_type="urn:ietf:params:oauth:token-type:access_token",
            envelope=parse_envelope(None),
        )

        assert result["ok"] is False
        assert "error" in result
