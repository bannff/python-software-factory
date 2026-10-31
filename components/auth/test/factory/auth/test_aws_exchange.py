"""Tests for CognitoAuthBackend.exchange_token() — authorization_code flow."""

import io
import json
import urllib.error

import pytest
from unittest.mock import MagicMock, patch

from factory.auth.runtime.envelope import Envelope


@pytest.fixture
def mock_boto3():
    with patch("boto3.client") as mc:
        mc.return_value = MagicMock()
        yield mc


@pytest.fixture
def envelope():
    return Envelope(principal_id="user-1", tenant_id="t-1")


def _make_backend(mock_boto3, **kwargs):
    from factory.auth.runtime.adapters.aws import CognitoAuthBackend

    defaults = dict(user_pool_id="us-east-1_ABC123", client_id="abc123def",
                    region="us-east-1")
    defaults.update(kwargs)
    return CognitoAuthBackend(**defaults)


def _mock_urlopen(response_data: dict):
    """Return a patch context that makes urlopen return *response_data* as JSON."""
    body = io.BytesIO(json.dumps(response_data).encode())
    body.read_side = None  # real BytesIO, no mock needed
    cm = MagicMock()
    cm.__enter__ = lambda s: body
    cm.__exit__ = MagicMock(return_value=False)
    return patch("urllib.request.urlopen", return_value=cm)


_TOKEN_RESP = {
    "access_token": "at-xyz", "id_token": "id-xyz",
    "refresh_token": "rt-xyz", "token_type": "Bearer", "expires_in": 3600,
}


# --- happy path ---

def test_exchange_auth_code_success(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://localhost:3000/callback")
    with _mock_urlopen(_TOKEN_RESP):
        r = backend.exchange_token(
            "auth-code-1", subject_token_type="authorization_code",
            requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is True
    assert r["access_token"] == "at-xyz"
    assert r["id_token"] == "id-xyz"
    assert r["refresh_token"] == "rt-xyz"
    assert r["token_type"] == "Bearer"
    assert r["expires_in"] == 3600


def test_exchange_auth_code_with_audience_as_redirect_uri(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://default/callback")
    with _mock_urlopen(_TOKEN_RESP) as mock_open:
        backend.exchange_token(
            "code-2", subject_token_type="authorization_code",
            requested_token_type=None, audience="http://custom/callback",
            scope=None, envelope=envelope)
        req = mock_open.call_args[0][0]
        body = req.data.decode()
    assert "redirect_uri=http://custom/callback" in body
    assert "http://default/callback" not in body


def test_exchange_auth_code_with_client_secret(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://localhost/cb",
                            client_secret="secret123")
    with _mock_urlopen(_TOKEN_RESP) as mock_open:
        backend.exchange_token(
            "code-3", subject_token_type="authorization_code",
            requested_token_type=None, audience=None, scope=None, envelope=envelope)
        req = mock_open.call_args[0][0]
        body = req.data.decode()
    assert "client_secret=secret123" in body


def test_exchange_auth_code_with_scope(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://localhost/cb")
    with _mock_urlopen(_TOKEN_RESP) as mock_open:
        backend.exchange_token(
            "code-s", subject_token_type="authorization_code",
            requested_token_type=None, audience=None, scope="openid profile",
            envelope=envelope)
        body = mock_open.call_args[0][0].data.decode()
    assert "scope=openid profile" in body


# --- configuration errors ---

def test_exchange_auth_code_missing_domain(mock_boto3, envelope):
    backend = _make_backend(mock_boto3)  # no domain
    r = backend.exchange_token(
        "code-4", subject_token_type="authorization_code",
        requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is False
    assert r["error"] == "configuration_error"
    assert "domain" in r["details"]


def test_exchange_auth_code_missing_redirect_uri(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain")  # no redirect_uri
    r = backend.exchange_token(
        "code-5", subject_token_type="authorization_code",
        requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is False
    assert r["error"] == "configuration_error"
    assert "redirect_uri" in r["details"]


# --- error handling ---

def test_exchange_auth_code_http_error(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://localhost/cb")
    err_body = json.dumps({"error": "invalid_grant",
                           "error_description": "Code expired"}).encode()
    http_err = urllib.error.HTTPError(
        url="https://x", code=400, msg="Bad Request",
        hdrs=MagicMock(), fp=io.BytesIO(err_body))
    with patch("urllib.request.urlopen", side_effect=http_err):
        r = backend.exchange_token(
            "bad-code", subject_token_type="authorization_code",
            requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is False
    assert r["error"] == "invalid_grant"
    assert r["error_description"] == "Code expired"


def test_exchange_auth_code_network_error(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain",
                            redirect_uri="http://localhost/cb")
    with patch("urllib.request.urlopen", side_effect=ConnectionError("refused")):
        r = backend.exchange_token(
            "code-6", subject_token_type="authorization_code",
            requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is False
    assert r["error"] == "backend_error"
    assert "ConnectionError" in r["details"]


# --- unsupported token types ---

def test_exchange_token_rfc8693_type_not_supported(mock_boto3, envelope):
    backend = _make_backend(mock_boto3, domain="my-domain")
    r = backend.exchange_token(
        "tok", subject_token_type="urn:ietf:params:oauth:token-type:access_token",
        requested_token_type=None, audience=None, scope=None, envelope=envelope)
    assert r["ok"] is False
    assert r["error"] == "not_supported"
