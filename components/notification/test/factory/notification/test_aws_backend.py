"""Tests for AWS notification backend — SNS/SES routing.

All boto3 calls are mocked — no real AWS resources needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.notification.runtime.models import (
    DeliveryStatus,
    NotificationRequest,
)


@pytest.fixture
def mock_sns() -> MagicMock:
    return MagicMock()


@pytest.fixture
def mock_ses() -> MagicMock:
    return MagicMock()


@pytest.fixture
def backend(mock_sns: MagicMock, mock_ses: MagicMock):
    """Create AWSNotificationBackend with mocked boto3 clients."""
    def client_factory(service: str, **kwargs):
        return {"sns": mock_sns, "ses": mock_ses}[service]

    with patch("boto3.client", side_effect=client_factory):
        from factory.notification.runtime.backends.aws import (
            AWSNotificationBackend,
        )

        return AWSNotificationBackend(
            region="us-east-1",
            sns_topic_arn="arn:aws:sns:us-east-1:123:test",
            ses_from_email="test@example.com",
        )


class TestAWSNotificationInit:
    """Initialization and properties."""

    def test_name_is_aws(self, backend) -> None:
        """Backend name is 'aws'."""
        assert backend.name == "aws"

    @pytest.mark.asyncio
    async def test_initialize_updates_config(self, backend) -> None:
        """initialize() updates SNS topic ARN and SES email."""
        await backend.initialize({
            "sns_topic_arn": "arn:new",
            "ses_from_email": "new@example.com",
        })
        assert backend._sns_topic_arn == "arn:new"
        assert backend._ses_from_email == "new@example.com"

    @pytest.mark.asyncio
    async def test_initialize_partial_config(self, backend) -> None:
        """initialize() with partial config only updates provided keys."""
        original_email = backend._ses_from_email
        await backend.initialize({"sns_topic_arn": "arn:updated"})
        assert backend._sns_topic_arn == "arn:updated"
        assert backend._ses_from_email == original_email

    @pytest.mark.asyncio
    async def test_initialize_empty_config(self, backend) -> None:
        """initialize() with empty config is a no-op."""
        original_arn = backend._sns_topic_arn
        await backend.initialize({})
        assert backend._sns_topic_arn == original_arn


class TestAWSNotificationSend:
    """send() routing to SNS vs SES."""

    @pytest.mark.asyncio
    async def test_send_sns_default(
        self, backend, mock_sns: MagicMock,
    ) -> None:
        """Default channel routes to SNS."""
        mock_sns.publish.return_value = {"MessageId": "msg-123"}
        request = NotificationRequest(recipient="user1", content="hello")
        result = await backend.send(request)
        assert result.status == "delivered"
        assert result.backend == "sns"

    @pytest.mark.asyncio
    async def test_send_ses_email(
        self, backend, mock_ses: MagicMock,
    ) -> None:
        """channel_id='email' routes to SES."""
        mock_ses.send_email.return_value = {"MessageId": "ses-456"}
        request = NotificationRequest(recipient="u@example.com", content="hi")
        # The adapter checks getattr(request, "channel", "sns")
        # Simulate email channel by setting attribute directly on instance dict
        object.__setattr__(request, "channel", "email")
        result = await backend.send(request)
        assert result.status == "delivered"
        assert result.backend == "ses"

    @pytest.mark.asyncio
    async def test_send_failure_returns_failed(
        self, backend, mock_sns: MagicMock,
    ) -> None:
        """Exception during send returns failed status."""
        mock_sns.publish.side_effect = Exception("throttled")
        request = NotificationRequest(recipient="user1", content="hi")
        result = await backend.send(request)
        assert result.status == "failed"


class TestAWSNotificationHealth:
    """health_check() and infrastructure_spec()."""

    @pytest.mark.asyncio
    async def test_health_check_healthy(
        self, backend, mock_sns: MagicMock,
    ) -> None:
        """Returns True when SNS list_topics succeeds."""
        mock_sns.list_topics.return_value = {"Topics": []}
        assert await backend.health_check() is True

    @pytest.mark.asyncio
    async def test_health_check_failure(
        self, backend, mock_sns: MagicMock,
    ) -> None:
        """Returns False when SNS call fails."""
        mock_sns.list_topics.side_effect = Exception("denied")
        assert await backend.health_check() is False

    def test_infrastructure_spec(self, backend) -> None:
        """Returns valid SNS+SES spec dict."""
        spec = backend.infrastructure_spec()
        assert "services" in spec
        services = {s["service"] for s in spec["services"]}
        assert services == {"sns", "ses"}
        for svc in spec["services"]:
            assert "construct" in svc
            assert "props" in svc

    def test_infrastructure_spec_ses_email(self, backend) -> None:
        """SES spec includes the configured from email."""
        spec = backend.infrastructure_spec()
        ses_svc = next(s for s in spec["services"] if s["service"] == "ses")
        assert ses_svc["props"]["email"] == "test@example.com"
