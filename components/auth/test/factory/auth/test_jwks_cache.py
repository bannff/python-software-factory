"""Tests for JWKS cache TTL behavior.

See also:
- test_jwks_network.py - Network failure tests
"""
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
    public_key = private_key.public_key()
    return private_key, public_key


def _make_jwks(public_key: Any, kid: str) -> dict[str, Any]:
    jwk_json = jwt.algorithms.RSAAlgorithm.to_jwk(public_key)
    jwk = json.loads(jwk_json)
    jwk.update({"kid": kid, "use": "sig", "alg": "RS256"})
    return {"keys": [jwk]}


def _make_token(private_key: Any, kid: str, claims: dict[str, Any]) -> str:
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": kid})


class TestJwksCacheTTL:
    """Test JWKS cache respects TTL settings."""

    def test_cache_hit_within_ttl(self) -> None:
        """JWKS should be cached and reused within TTL."""
        private_key, public_key = _make_rsa_keypair()
        kid = "cache-test-kid"
        jwks = _make_jwks(public_key, kid)
        fetch_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal fetch_count
            fetch_count += 1
            return httpx.Response(200, json=jwks)

        client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
        cfg = KeycloakBackendConfig(
            schema_version=1,
            kind="keycloak",
            base_url="http://kc",
            realm="r",
            issuer="http://issuer",
            jwks_url="http://jwks",
            jwks_cache_ttl_seconds=300,
        )
        backend = KeycloakBackend(cfg, http=client)

        now = int(time.time())
        token = _make_token(
            private_key, kid, {"iss": "http://issuer", "exp": now + 60, "sub": "user-1"}
        )
        env = parse_envelope(None)

        # First call fetches JWKS
        result1 = backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert result1["ok"] is True
        assert fetch_count == 1

        # Second call should use cache
        result2 = backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert result2["ok"] is True
        assert fetch_count == 1  # No additional fetch

    def test_cache_miss_after_ttl(self) -> None:
        """JWKS should be refetched after TTL expires."""
        private_key, public_key = _make_rsa_keypair()
        kid = "cache-test-kid"
        jwks = _make_jwks(public_key, kid)
        fetch_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal fetch_count
            fetch_count += 1
            return httpx.Response(200, json=jwks)

        client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
        cfg = KeycloakBackendConfig(
            schema_version=1,
            kind="keycloak",
            base_url="http://kc",
            realm="r",
            issuer="http://issuer",
            jwks_url="http://jwks",
            jwks_cache_ttl_seconds=1,  # 1 second TTL
        )
        backend = KeycloakBackend(cfg, http=client)

        now = int(time.time())
        token = _make_token(
            private_key, kid, {"iss": "http://issuer", "exp": now + 60, "sub": "user-1"}
        )
        env = parse_envelope(None)

        # First call fetches JWKS
        result1 = backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert result1["ok"] is True
        assert fetch_count == 1

        # Wait for TTL to expire
        time.sleep(1.1)

        # Third call should refetch
        result2 = backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert result2["ok"] is True
        assert fetch_count == 2  # Refetched after TTL

    def test_cache_disabled_with_zero_ttl(self) -> None:
        """JWKS should be fetched every time when TTL is 0."""
        private_key, public_key = _make_rsa_keypair()
        kid = "cache-test-kid"
        jwks = _make_jwks(public_key, kid)
        fetch_count = 0

        def handler(request: httpx.Request) -> httpx.Response:
            nonlocal fetch_count
            fetch_count += 1
            return httpx.Response(200, json=jwks)

        client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)
        cfg = KeycloakBackendConfig(
            schema_version=1,
            kind="keycloak",
            base_url="http://kc",
            realm="r",
            issuer="http://issuer",
            jwks_url="http://jwks",
            jwks_cache_ttl_seconds=0,  # Disabled
        )
        backend = KeycloakBackend(cfg, http=client)

        now = int(time.time())
        token = _make_token(
            private_key, kid, {"iss": "http://issuer", "exp": now + 60, "sub": "user-1"}
        )
        env = parse_envelope(None)

        # Each call should fetch JWKS
        backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert fetch_count == 1

        backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert fetch_count == 2

        backend.verify_access_token(
            token, required_audience=None, required_scopes=None, envelope=env
        )
        assert fetch_count == 3
