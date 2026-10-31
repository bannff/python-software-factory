"""Deterministic, no-network email sender for tests and local workflows."""
from __future__ import annotations

import hashlib

from factory.integrations.runtime.email_models import (
    EmailIdempotencyConflict, EmailReceipt, SendEmailRequest,
)


class FakeEmailSender:
    """Produce stable receipts while rejecting conflicting key reuse."""

    def __init__(self) -> None:
        self._receipts: dict[str, EmailReceipt] = {}
        self._intent_digests: dict[str, str] = {}
        self.send_count = 0

    def send(
        self, request: SendEmailRequest,
    ) -> EmailReceipt | EmailIdempotencyConflict:
        key = request.idempotency_key
        digest = request.intent_digest()
        prior_digest = self._intent_digests.get(key)
        if prior_digest is not None:
            if prior_digest != digest:
                return EmailIdempotencyConflict(status="idempotency_conflict")
            return self._receipts[key]
        self.send_count += 1
        receipt = EmailReceipt(
            status="sent",
            message_id="fake-" + hashlib.sha256(
                key.encode(), usedforsecurity=False,
            ).hexdigest()[:32],
            intent_digest=digest,
        )
        self._intent_digests[key] = digest
        self._receipts[key] = receipt
        return receipt
