"""AWS identity probe adapter.

Probes the active boto3 session to discover AWS identity:
profile, region, account_id, and identity ARN. Caches results
with a configurable TTL. Degrades gracefully when no creds exist.
"""

from __future__ import annotations

import importlib.util
import logging
import os
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)

BOTO3_AVAILABLE = importlib.util.find_spec("boto3") is not None

_DEFAULT_TTL = 300  # 5 minutes


@dataclass(frozen=True)
class AWSIdentity:
    """Immutable snapshot of the active AWS identity."""

    available: bool = False
    profile: str | None = None
    region: str | None = None
    account_id: str | None = None
    identity_arn: str | None = None
    user_id: str | None = None
    error: str | None = None
    probed_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict for MCP responses."""
        return {
            "available": self.available,
            "profile": self.profile,
            "region": self.region,
            "account_id": self.account_id,
            "identity_arn": self.identity_arn,
            "user_id": self.user_id,
            "error": self.error,
        }


_UNAVAILABLE = AWSIdentity(error="boto3 not installed")


class AWSIdentityProbe:
    """Probes boto3 session for active AWS identity. Caches with TTL."""

    def __init__(self, ttl_seconds: float = _DEFAULT_TTL) -> None:
        self._ttl = ttl_seconds
        self._cached: AWSIdentity | None = None

    def probe(self, force: bool = False) -> AWSIdentity:
        """Probe AWS identity. Returns cached result if within TTL."""
        if not BOTO3_AVAILABLE:
            return _UNAVAILABLE
        if not force and self._cached and self._is_fresh():
            return self._cached
        self._cached = self._do_probe()
        return self._cached

    def invalidate(self) -> None:
        """Clear cached identity."""
        self._cached = None

    def _is_fresh(self) -> bool:
        if self._cached is None:
            return False
        return (time.time() - self._cached.probed_at) < self._ttl

    def _do_probe(self) -> AWSIdentity:
        """Execute the actual boto3 probe."""
        import boto3

        now = time.time()
        try:
            session = boto3.Session()
            profile = session.profile_name
            region = (
                session.region_name
                or os.environ.get("AWS_REGION")
                or os.environ.get("AWS_DEFAULT_REGION")
            )
            creds = session.get_credentials()
            if creds is None:
                return AWSIdentity(
                    available=False,
                    profile=profile,
                    region=region,
                    error="No AWS credentials found",
                    probed_at=now,
                )
            # Resolve to get actual access key (validates creds exist)
            creds.get_frozen_credentials()
            sts = session.client("sts", region_name=region or "us-east-1")
            identity = sts.get_caller_identity()
            return AWSIdentity(
                available=True,
                profile=profile if profile != "default" else profile,
                region=region,
                account_id=identity.get("Account"),
                identity_arn=identity.get("Arn"),
                user_id=identity.get("UserId"),
                probed_at=now,
            )
        except Exception as e:
            logger.debug("AWS identity probe failed: %s", e)
            return AWSIdentity(
                available=False,
                error=str(e),
                probed_at=now,
            )
