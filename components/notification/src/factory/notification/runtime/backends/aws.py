"""AWS adapter for notification brick.

Supports SNS (push/SMS) and SES (email) channels.
"""

from __future__ import annotations

from typing import Any

from factory.notification.runtime.models import (
    DeliveryStatus,
    NotificationRequest,
)


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS notification adapter"
        raise ImportError(msg)


class AWSNotificationBackend:
    """AWS adapter — routes to SNS or SES based on channel type."""

    def __init__(
        self,
        region: str = "us-east-1",
        sns_topic_arn: str = "",
        ses_from_email: str = "noreply@example.com",
        **kwargs: Any,
    ) -> None:
        _require_boto3()
        import boto3

        self._region = region
        self._sns_topic_arn = sns_topic_arn
        self._ses_from_email = ses_from_email
        self._sns = boto3.client("sns", region_name=region)
        self._ses = boto3.client("ses", region_name=region)

    @property
    def name(self) -> str:
        return "aws"

    async def initialize(self, config: dict[str, Any]) -> None:
        if "sns_topic_arn" in config:
            self._sns_topic_arn = config["sns_topic_arn"]
        if "ses_from_email" in config:
            self._ses_from_email = config["ses_from_email"]

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        """Route to SNS or SES based on channel."""
        channel = getattr(request, "channel", "sns")
        try:
            if channel == "email":
                return await self._send_ses(request)
            return await self._send_sns(request)
        except Exception as e:
            return DeliveryStatus(
                message_id=getattr(request, "id", "unknown"),
                backend="aws",
                status="failed",
                error=str(e),
            )

    async def _send_sns(self, request: NotificationRequest) -> DeliveryStatus:
        resp = self._sns.publish(
            TopicArn=self._sns_topic_arn,
            Message=request.content or "",
            Subject=request.subject or "Notification",
        )
        return DeliveryStatus(
            message_id=resp.get("MessageId", ""),
            backend="sns",
            status="delivered",
            recipient=request.recipient,
        )

    async def _send_ses(self, request: NotificationRequest) -> DeliveryStatus:
        resp = self._ses.send_email(
            Source=self._ses_from_email,
            Destination={"ToAddresses": [request.recipient]},
            Message={
                "Subject": {"Data": request.subject or ""},
                "Body": {"Text": {"Data": request.content or ""}},
            },
        )
        return DeliveryStatus(
            message_id=resp.get("MessageId", ""),
            backend="ses",
            status="delivered",
            recipient=request.recipient,
        )

    async def health_check(self) -> bool:
        try:
            self._sns.list_topics(MaxItems="1")
            return True
        except Exception:
            return False

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "services": [
                {
                    "service": "sns",
                    "construct": "Topic",
                    "props": {"topic_name": "factory-notifications"},
                },
                {
                    "service": "ses",
                    "construct": "EmailIdentity",
                    "props": {"email": self._ses_from_email},
                },
            ],
        }
