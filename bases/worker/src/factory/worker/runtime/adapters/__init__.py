"""Worker adapters — shared constants and utilities."""

import re

QUEUE_URL_RE = re.compile(r"^https://sqs\.[\w-]+\.amazonaws\.com/\d{12}/[\w-]+$")


def require_boto3() -> None:
    """Raise ImportError if boto3 is not installed."""
    try:
        import boto3  # noqa: F401
    except ImportError:
        raise ImportError("pip install boto3 — required for AWS worker adapters")
