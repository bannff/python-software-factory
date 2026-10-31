"""Tests for Cognito token verification, introspection, and refresh."""

import pytest
from unittest.mock import MagicMock, patch

from factory.auth.runtime.envelope import Envelope


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def backend(mock_boto3):
    from factory.auth.runtime.adapters.aws import CognitoAuthBackend

    return CognitoAuthBackend(
        user_pool_id="us-east-1_ABC123", client_id="abc123def",
    )


@pytest.fixture
def envelope():
    return Envelope(principal_id="user-1", tenant_id="t-1")


def test_verify_access_token_valid(backend, envelope):
    mock_key = MagicMock()
    mock_key.key_id = "kid-1"
    mock_key.key = "fake-key"
    mock_jwk_set = MagicMock()
    mock_jwk_set.keys = [mock_key]
    claims = {
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ABC123",
        "token_use": "access", "sub": "u-1", "username": "alice",
        "scope": "read write",
    }
    with patch.object(backend, "_get_jwks", return_value={"keys": []}), \
         patch("jwt.get_unverified_header", return_value={"kid": "kid-1"}), \
         patch("jwt.PyJWKSet.from_dict", return_value=mock_jwk_set), \
         patch("jwt.decode", return_value=claims):
        r = backend.verify_access_token(
            "tok", required_audience=None, required_scopes=None, envelope=envelope,
        )
    assert r["ok"] is True
    assert r["principal"]["username"] == "alice"
    assert r["principal"]["subject"] == "u-1"


def test_verify_access_token_missing_kid(backend, envelope):
    with patch.object(backend, "_get_jwks", return_value={"keys": []}), \
         patch("jwt.get_unverified_header", return_value={}):
        r = backend.verify_access_token(
            "tok", required_audience=None, required_scopes=None, envelope=envelope,
        )
    assert r["ok"] is False
    assert r["error"] == "missing_kid"


def test_verify_access_token_unknown_kid(backend, envelope):
    mock_jwk_set = MagicMock()
    mock_jwk_set.keys = []
    with patch.object(backend, "_get_jwks", return_value={"keys": []}), \
         patch("jwt.get_unverified_header", return_value={"kid": "unknown"}), \
         patch("jwt.PyJWKSet.from_dict", return_value=mock_jwk_set):
        r = backend.verify_access_token(
            "tok", required_audience=None, required_scopes=None, envelope=envelope,
        )
    assert r["ok"] is False
    assert r["error"] == "unknown_kid"


def test_verify_access_token_missing_scopes(backend, envelope):
    mock_key = MagicMock()
    mock_key.key_id = "kid-1"
    mock_jwk_set = MagicMock()
    mock_jwk_set.keys = [mock_key]
    claims = {
        "iss": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_ABC123",
        "token_use": "access", "scope": "read",
    }
    with patch.object(backend, "_get_jwks", return_value={"keys": []}), \
         patch("jwt.get_unverified_header", return_value={"kid": "kid-1"}), \
         patch("jwt.PyJWKSet.from_dict", return_value=mock_jwk_set), \
         patch("jwt.decode", return_value=claims):
        r = backend.verify_access_token(
            "tok", required_audience=None,
            required_scopes=["read", "admin"], envelope=envelope,
        )
    assert r["ok"] is False
    assert "admin" in r["missing"]


def test_verify_access_token_exception(backend, envelope):
    with patch("jwt.get_unverified_header", side_effect=Exception("bad token")):
        r = backend.verify_access_token(
            "tok", required_audience=None, required_scopes=None, envelope=envelope,
        )
    assert r["ok"] is False
    assert r["error"] == "invalid_token"


def test_introspect_token_active(backend, envelope):
    with patch.object(backend, "verify_access_token", return_value={
        "ok": True, "claims": {"sub": "u-1", "exp": 9999, "scope": "read"},
    }):
        r = backend.introspect_token("tok", envelope=envelope)
    assert r["active"] is True
    assert r["sub"] == "u-1"


def test_introspect_token_inactive(backend, envelope):
    with patch.object(backend, "verify_access_token", return_value={
        "ok": False, "error": "expired",
    }):
        r = backend.introspect_token("tok", envelope=envelope)
    assert r["active"] is False


def test_refresh_token_success(backend, envelope):
    backend._client.admin_initiate_auth.return_value = {
        "AuthenticationResult": {
            "AccessToken": "new-at", "TokenType": "Bearer", "ExpiresIn": 3600,
        },
    }
    r = backend.refresh_token("rt-1", envelope=envelope)
    assert r["ok"] is True
    assert r["access_token"] == "new-at"


def test_refresh_token_failure(backend, envelope):
    backend._client.admin_initiate_auth.side_effect = Exception("bad refresh")
    r = backend.refresh_token("rt-1", envelope=envelope)
    assert r["ok"] is False


def test_revoke_token_success(backend, envelope):
    backend._client.revoke_token.return_value = {}
    r = backend.revoke_token("tok", envelope=envelope)
    assert r["ok"] is True


def test_revoke_token_failure(backend, envelope):
    backend._client.revoke_token.side_effect = Exception("revoke err")
    r = backend.revoke_token("tok", envelope=envelope)
    assert r["ok"] is False
