"""Tests for AWS identity probe adapter."""

from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

from factory.config.runtime.adapters.aws_identity import (
    AWSIdentity,
    AWSIdentityProbe,
    _UNAVAILABLE,
)


class TestAWSIdentity:
    """Test AWSIdentity dataclass."""

    def test_default_unavailable(self):
        identity = AWSIdentity()
        assert identity.available is False
        assert identity.to_dict()["available"] is False

    def test_to_dict_keys(self):
        identity = AWSIdentity(
            available=True,
            profile="dev",
            region="us-west-2",
            account_id="123456789012",
            identity_arn="arn:aws:iam::123456789012:user/test",
            user_id="AIDA123",
        )
        d = identity.to_dict()
        assert d["available"] is True
        assert d["profile"] == "dev"
        assert d["region"] == "us-west-2"
        assert d["account_id"] == "123456789012"
        assert d["identity_arn"] == "arn:aws:iam::123456789012:user/test"
        assert d["error"] is None

    def test_unavailable_sentinel(self):
        assert _UNAVAILABLE.available is False
        assert _UNAVAILABLE.error == "boto3 not installed"


def _make_mock_session(
    profile: str = "test",
    region: str = "us-east-1",
    account: str = "123456789012",
    arn: str = "arn:aws:iam::123456789012:user/test",
    user_id: str = "AIDA123",
    has_creds: bool = True,
):
    """Build a mock boto3.Session with STS."""
    session = MagicMock()
    session.profile_name = profile
    session.region_name = region
    if has_creds:
        creds = MagicMock()
        session.get_credentials.return_value = creds
        sts = MagicMock()
        sts.get_caller_identity.return_value = {
            "Account": account,
            "Arn": arn,
            "UserId": user_id,
        }
        session.client.return_value = sts
    else:
        session.get_credentials.return_value = None
    return session


class TestAWSIdentityProbe:
    """Test AWSIdentityProbe with mocked boto3."""

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", False)
    def test_no_boto3_returns_unavailable(self):
        probe = AWSIdentityProbe()
        result = probe.probe()
        assert result.available is False
        assert result.error == "boto3 not installed"

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", True)
    @patch("boto3.Session")
    def test_successful_probe(self, mock_session_cls):
        mock_session_cls.return_value = _make_mock_session(
            profile="my-profile", region="us-west-2",
        )
        probe = AWSIdentityProbe()
        result = probe.probe()
        assert result.available is True
        assert result.profile == "my-profile"
        assert result.region == "us-west-2"
        assert result.account_id == "123456789012"

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", True)
    @patch("boto3.Session")
    def test_no_credentials(self, mock_session_cls):
        mock_session_cls.return_value = _make_mock_session(has_creds=False)
        probe = AWSIdentityProbe()
        result = probe.probe()
        assert result.available is False
        assert "No AWS credentials" in result.error

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", True)
    @patch("boto3.Session")
    def test_caching_respects_ttl(self, mock_session_cls):
        mock_session_cls.return_value = _make_mock_session()
        probe = AWSIdentityProbe(ttl_seconds=60)
        r1 = probe.probe()
        r2 = probe.probe()
        assert mock_session_cls.call_count == 1
        assert r1 is r2

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", True)
    @patch("boto3.Session")
    def test_force_refresh_bypasses_cache(self, mock_session_cls):
        mock_session_cls.return_value = _make_mock_session()
        probe = AWSIdentityProbe(ttl_seconds=60)
        probe.probe()
        probe.probe(force=True)
        assert mock_session_cls.call_count == 2

    @patch("factory.config.runtime.adapters.aws_identity.BOTO3_AVAILABLE", True)
    @patch("boto3.Session", side_effect=Exception("kaboom"))
    def test_exception_returns_unavailable(self, mock_session_cls):
        probe = AWSIdentityProbe()
        result = probe.probe()
        assert result.available is False
        assert "kaboom" in result.error

    def test_invalidate_clears_cache(self):
        probe = AWSIdentityProbe()
        probe._cached = AWSIdentity(available=True, probed_at=time.time())
        probe.invalidate()
        assert probe._cached is None
