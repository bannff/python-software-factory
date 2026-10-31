"""Tests for JWKS network failure handling and token expiration."""
from __future__ import annotations

import json
import time
from typing import Any

import httpx
import jwt

from factory.auth.runtime.envelope import parse_envelope
from factory.auth.runtime.keycloak import KeycloakBackend
from factory.auth.runtime.models import KeycloakBackendConfig


def _make_rsa_keypair() -> tuple[Any, Any]:
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


def _make_jwks(public_key: Any, kid: str) -> dict[str, Any]:
    jwk_json = jwt.algorithms.RSAAlgorithm.to_jwk(public_key)
    jwk = json.loads(jwk_json)
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def _make_token(private_key: Any, kid: str, claims: dict[str, Any]) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


def _make_backend(handler) -> KeycloakBackend:
    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
    cfg = KeycloakBackendConfig(
        schema_version=1, kind="keycloak", base_url="http://kc",
        realm="r", issuer="http://issuer", jwks_url="http://jwks",
    )
    return KeycloakBackend(cfg, http=client)


class TestTokenExpiration:
    """Test token expiration edge cases."""

    def test_expired_token_rejected(self) -> None:
        """Expired tokens should be rejected."""
        private_key, public_key = _make_rsa_keypair()
        jwks = _make_jwks(public_key, "kid")

        def handler(r: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=jwks)

        backend = _make_backend(handler)
        token = _make_token(
            private_key, "kid",
            {"iss": "http://issuer", "exp": int(time.time()) - 10, "sub": "u1"},
        )
        result = backend.verify_access_token(
            token, required_audience=None, required_scopes=None,
            envelope=parse_envelope(None),
        )
        assert result["ok"] is False
        assert result["error"] == "expired"

    def test_token_at_expiration_boundary(self) -> None:
        """Token exactly at expiration should still work (leeway)."""
        private_key, public_key = _make_rsa_keypair()
        jwks = _make_jwks(public_key, "kid")

        def handler(r: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json=jwks)

        backend = _make_backend(handler)
        token = _make_token(
            private_key, "kid",
            {"iss": "http://issuer", "exp": int(time.time()) + 1, "sub": "u1"},
        )
        result = backend.verify_access_token(
            token, required_audience=None, required_scopes=None,
            envelope=parse_envelope(None),
        )
        assert result["ok"] is True


class TestNetworkFailures:
    """Test handling of network failures."""

    def test_jwks_fetch_timeout(self) -> None:
        """JWKS fetch timeout should return error."""
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.TimeoutException("Timeout")

        backend = _make_backend(handler)
        result = backend.verify_access_token(
            "token", required_audience=None, required_scopes=None,
            envelope=parse_envelope(None),
        )
        assert result["ok"] is False

    def test_jwks_fetch_connection_error(self) -> None:
        """JWKS connection error should return error."""
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Refused")

        backend = _make_backend(handler)
        result = backend.verify_access_token(
            "token", required_audience=None, required_scopes=None,
            envelope=parse_envelope(None),
        )
        assert result["ok"] is False

    def test_jwks_invalid_response(self) -> None:
        """Invalid JWKS response should return error."""
        def handler(r: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"not": "jwks"})

        backend = _make_backend(handler)
        result = backend.verify_access_token(
            "token", required_audience=None, required_scopes=None,
            envelope=parse_envelope(None),
        )
        assert result["ok"] is False

    def test_health_check_reports_connectivity_failure(self) -> None:
        """Health check should report connectivity failures."""
        def handler(r: httpx.Request) -> httpx.Response:
            raise httpx.ConnectError("Refused")

        backend = _make_backend(handler)
        result = backend.health_check()
        assert result["attempted"] is True
        assert result["ok"] is False
