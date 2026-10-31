"""Tests for AuthlibKeycloakBackend adapter (authlib library).

Tests JWT verification and JWKS handling with mocked HTTP responses.
Uses real authlib crypto for key generation and token signing.
"""

from __future__ import annotations

import time

import pytest
from unittest.mock import MagicMock

from authlib.jose import JsonWebKey, jwt as authlib_jwt

from factory.auth.runtime.adapters.authlib_keycloak import AuthlibKeycloakBackend
from factory.auth.runtime.envelope import Envelope
from factory.auth.runtime.models import KeycloakBackendConfig


def _make_jwk_pair():
    """Generate an RSA key pair for testing."""
    key = JsonWebKey.generate_key("RSA", 2048, is_private=True)
    private_jwk = key.as_dict(is_private=True)
    public_jwk = key.as_dict(is_private=False)
    public_jwk["kid"] = "test-kid"
    private_jwk["kid"] = "test-kid"
    return private_jwk, public_jwk


def _sign_token(private_jwk: dict, claims: dict) -> str:
    """Sign a JWT with the given private key."""
    header = {"alg": "RS256", "kid": private_jwk["kid"]}
    return authlib_jwt.encode(header, claims, private_jwk).decode("utf-8")


@pytest.fixture
def keys():
    return _make_jwk_pair()


@pytest.fixture
def config() -> KeycloakBackendConfig:
    return KeycloakBackendConfig(
        kind="keycloak",
        base_url="https://keycloak.example.com",
        realm="test-realm",
        client_id="test-client",
    )


@pytest.fixture
def backend(config, keys):
    """Backend with mocked HTTP that returns our test JWKS."""
    _, public_jwk = keys
    mock_http = MagicMock()
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"keys": [public_jwk]}
    mock_resp.raise_for_status = MagicMock()
    mock_http.get.return_value = mock_resp
    return AuthlibKeycloakBackend(config, http=mock_http)


class TestAuthlibKeycloakBackend:
    """Tests for AuthlibKeycloakBackend using real authlib crypto."""

    def test_import(self) -> None:
        """Adapter and authlib are importable."""
        from authlib.jose import jwt
        assert jwt is not None
        assert AuthlibKeycloakBackend is not None

    def test_health_check(self, backend: AuthlibKeycloakBackend) -> None:
        """health_check fetches JWKS and reports ok."""
        health = backend.health_check()
        assert health["ok"] is True
        assert "jwks_url" in health

    def test_jwks_fetched_from_http(self, backend: AuthlibKeycloakBackend) -> None:
        """JWKS is fetched via the HTTP client."""
        backend._get_jwks()
        backend._http.get.assert_called_once()

    def test_jwks_cached(self, backend: AuthlibKeycloakBackend) -> None:
        """JWKS is cached after first fetch."""
        backend._get_jwks()
        backend._get_jwks()
        # Should only call HTTP once due to caching
        assert backend._http.get.call_count == 1

    def test_token_decode_with_real_crypto(self, keys) -> None:
        """authlib can sign and decode a JWT with real RSA keys."""
        private_jwk, public_jwk = keys
        now = int(time.time())
        claims = {"sub": "user-42", "exp": now + 3600, "iat": now}
        token = _sign_token(private_jwk, claims)

        key_set = JsonWebKey.import_key_set({"keys": [public_jwk]})
        decoded = authlib_jwt.decode(token, key_set)
        assert decoded["sub"] == "user-42"

    def test_verify_expired_token(self, backend, keys) -> None:
        """Expired JWT fails verification."""
        private_jwk, _ = keys
        now = int(time.time())
        claims = {
            "sub": "user-42",
            "iss": backend.cfg.effective_issuer(),
            "exp": now - 3600,  # expired
            "iat": now - 7200,
        }
        token = _sign_token(private_jwk, claims)
        envelope = Envelope()

        result = backend.verify_access_token(
            token, required_audience=None,
            required_scopes=None, envelope=envelope,
        )
        assert result["ok"] is False

    def test_verify_garbage_token(self, backend) -> None:
        """Garbage token fails verification."""
        envelope = Envelope()
        result = backend.verify_access_token(
            "not.a.valid.jwt", required_audience=None,
            required_scopes=None, envelope=envelope,
        )
        assert result["ok"] is False

    def test_introspect_expired_token(self, backend, keys) -> None:
        """introspect_token returns active=False for expired token."""
        private_jwk, _ = keys
        now = int(time.time())
        claims = {"sub": "user-42", "exp": now - 100, "iat": now - 200}
        token = _sign_token(private_jwk, claims)
        envelope = Envelope()

        result = backend.introspect_token(token, envelope=envelope)
        assert result["active"] is False

    def test_resolve_principal_from_envelope(self, backend) -> None:
        """resolve_principal uses envelope principal_id."""
        envelope = Envelope(principal_id="user-99", tenant_id="t1")
        result = backend.resolve_principal(envelope=envelope)
        assert result["ok"] is True
        assert result["principal"]["subject"] == "user-99"

    def test_resolve_principal_unknown(self, backend) -> None:
        """resolve_principal with empty envelope returns unknown source."""
        envelope = Envelope()
        result = backend.resolve_principal(envelope=envelope)
        assert result["ok"] is True
        assert result["source"] == "unknown"
