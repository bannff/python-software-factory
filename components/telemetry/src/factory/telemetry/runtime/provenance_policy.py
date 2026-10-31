"""Server-owned redaction and sampling policy for provenance retention."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
from typing import Literal

from .provenance_models import AuthenticatedTelemetryContext, TelemetryIngestItem

PolicyOutcome = Literal["retained", "redacted", "sampled_out"]


@dataclass(frozen=True)
class PolicyDecision:
    item: TelemetryIngestItem | None
    outcome: PolicyOutcome
    evidence: dict[str, object]


@dataclass(frozen=True)
class RetentionPolicy:
    """Immutable policy configured by the Telemetry server, never by callers."""

    version: str = "telemetry-default-v1"
    sample_rate: float = 1.0
    redact_fields: frozenset[str] = frozenset()

    def __post_init__(self) -> None:
        if not self.version or not isinstance(self.version, str):
            raise ValueError("policy version is required")
        if not 0.0 <= self.sample_rate <= 1.0:
            raise ValueError("sample_rate must be between 0 and 1")
        if any(not field or not isinstance(field, str) for field in self.redact_fields):
            raise ValueError("redact_fields must contain non-empty strings")

    def apply(
        self, context: AuthenticatedTelemetryContext, item: TelemetryIngestItem,
    ) -> PolicyDecision:
        evidence: dict[str, object] = {
            "policy_version": self.version,
            "sample_rate": self.sample_rate,
            "redacted_fields": [],
        }
        if self._sampled_out(context, item):
            evidence["outcome"] = "sampled_out"
            evidence["sampled_out"] = True
            return PolicyDecision(None, "sampled_out", evidence)
        payload = _redact(item.canonical_payload, self.redact_fields)
        attributes = _redact(item.attributes, self.redact_fields)
        redacted = payload != item.canonical_payload or attributes != item.attributes
        outcome: PolicyOutcome = "redacted" if redacted else "retained"
        evidence["outcome"] = outcome
        evidence["redacted_fields"] = sorted(self.redact_fields) if redacted else []
        return PolicyDecision(
            item.model_copy(update={"canonical_payload": payload, "attributes": attributes}),
            outcome,
            evidence,
        )

    def _sampled_out(self, context: AuthenticatedTelemetryContext, item: TelemetryIngestItem) -> bool:
        if self.sample_rate >= 1.0:
            return False
        if self.sample_rate <= 0.0:
            return True
        key = f"{context.tenant_id}\0{context.producer_id}\0{item.source_id}".encode()
        value = int.from_bytes(hashlib.sha256(key).digest(), "big") / 2**256
        return value >= self.sample_rate


def _redact(value: object, fields: frozenset[str]) -> object:
    if isinstance(value, dict):
        return {
            key: "[REDACTED]" if key in fields else _redact(item, fields)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_redact(item, fields) for item in value]
    return value


__all__ = ["PolicyDecision", "PolicyOutcome", "RetentionPolicy"]
