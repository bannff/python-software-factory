"""Tests for Cognito auth backend — constructor, health, user info, infra."""

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


def test_kind(backend):
    assert backend.kind == "cognito"


def test_invalid_pool_id(mock_boto3):
    from factory.auth.runtime.adapters.aws import CognitoAuthBackend

    with pytest.raises(ValueError, match="Invalid user_pool_id"):
        CognitoAuthBackend(user_pool_id="bad!!!", client_id="abc123")


def test_invalid_client_id(mock_boto3):
    from factory.auth.runtime.adapters.aws import CognitoAuthBackend

    with pytest.raises(ValueError, match="Invalid client_id"):
        CognitoAuthBackend(user_pool_id="us-east-1_ABC123", client_id="bad!!!")


def test_health_check_ok(backend):
    backend._client.describe_user_pool.return_value = {
        "UserPool": {"Name": "my-pool"},
    }
    h = backend.health_check()
    assert h["ok"] is True
    assert h["pool_name"] == "my-pool"


def test_health_check_error(backend):
    backend._client.describe_user_pool.side_effect = RuntimeError("fail")
    h = backend.health_check()
    assert h["ok"] is False


def test_resolve_principal_from_envelope(backend, envelope):
    r = backend.resolve_principal(envelope=envelope)
    assert r["ok"] is True
    assert r["principal"]["subject"] == "user-1"


def test_resolve_principal_empty(backend):
    r = backend.resolve_principal(envelope=Envelope())
    assert r["principal"] is None


def test_get_user_info(backend, envelope):
    backend._client.get_user.return_value = {
        "Username": "alice",
        "UserAttributes": [{"Name": "email", "Value": "[email protected]"}],
    }
    r = backend.get_user_info("at-1", envelope=envelope)
    assert r["ok"] is True
    assert r["user_info"]["username"] == "alice"


def test_exchange_token_not_supported(backend, envelope):
    r = backend.exchange_token(
        "tok", subject_token_type="jwt",
        requested_token_type=None, audience=None, scope=None, envelope=envelope,
    )
    assert r["ok"] is False
    assert r["error"] == "not_supported"


def test_infrastructure_spec(backend):
    spec = backend.infrastructure_spec()
    assert spec["provider"] == "aws"
    assert spec["service"] == "cognito-idp"
    assert len(spec["resources"]) == 2


def test_secret_hash_with_secret(mock_boto3):
    from factory.auth.runtime.adapters.aws import CognitoAuthBackend

    b = CognitoAuthBackend(
        user_pool_id="us-east-1_ABC123", client_id="abc123",
        client_secret="mysecret",
    )
    h = b._secret_hash("alice")
    assert h is not None and len(h) > 0


def test_secret_hash_without_secret(backend):
    assert backend._secret_hash("alice") is None
