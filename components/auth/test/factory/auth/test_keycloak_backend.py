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


def test_verify_access_token_and_scopes() -> None:
    private_key, public_key = _make_rsa_keypair()
    kid = "testkid"
    jwks = _make_jwks(public_key, kid)

    def handler(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "http://jwks"
        return httpx.Response(200, json=jwks)

    client = httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0)

    cfg = KeycloakBackendConfig(
        schema_version=1,
        kind="keycloak",
        base_url="http://kc",
        realm="r",
        issuer="http://issuer",
        jwks_url="http://jwks",
        default_audience="aud",
        tenant_claim="tenant_id",
    )

    backend = KeycloakBackend(cfg, http=client)

    now = int(time.time())
    token = jwt.encode(
        {
            "iss": cfg.effective_issuer(),
            "aud": "aud",
            "exp": now + 60,
            "sub": "user-1",
            "scope": "read write",
            "tenant_id": "t1",
            "preferred_username": "u1",
        },
        private_key,
        algorithm="RS256",
        headers={"kid": kid},
    )

    env = parse_envelope({"tenant_id": "t1"})
    ok = backend.verify_access_token(token, required_audience=None, required_scopes=["read"], envelope=env)
    assert ok["ok"] is True
    assert ok["principal"]["tenant_id"] == "t1"

    missing = backend.verify_access_token(token, required_audience=None, required_scopes=["admin"], envelope=env)
    assert missing["ok"] is False
    assert missing["error"] == "missing_scopes"

    mismatch = backend.verify_access_token(
        token, required_audience=None, required_scopes=None, envelope=parse_envelope({"tenant_id": "t2"})
    )
    assert mismatch["ok"] is False
    assert mismatch["error"] == "tenant_mismatch"


def test_introspect_invalid_token() -> None:
    cfg = KeycloakBackendConfig(schema_version=1, kind="keycloak", base_url="http://kc", realm="r")

    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"keys": []})

    backend = KeycloakBackend(cfg, http=httpx.Client(transport=httpx.MockTransport(handler), timeout=1.0))
    res = backend.introspect_token("not-a-jwt", envelope=parse_envelope(None))
    assert res["active"] is False
