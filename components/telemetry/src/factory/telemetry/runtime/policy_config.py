"""Operator-configured telemetry retention, composed from env at construction time.

Mirrors the FACTORY_BROWSER_ADAPTER / FACTORY_SECURITY_ADAPTER pattern: the
operator sets an env var before starting the process; nothing here is a
per-owner toggle. Sampling and redaction stay server-owned (RetentionPolicy
docstring), and a bad env value fails closed to the safe default rather than
silently widening collection.
"""
from __future__ import annotations

import os

from .provenance_policy import RetentionPolicy

SAMPLE_RATE_ENV = "TELEMETRY_SAMPLE_RATE"
REDACT_FIELDS_ENV = "TELEMETRY_REDACT_FIELDS"
RAW_DAYS_ENV = "TELEMETRY_RAW_DAYS"
ROLLUP_DAYS_ENV = "TELEMETRY_ROLLUP_DAYS"

DEFAULT_RAW_DAYS = 7
DEFAULT_ROLLUP_DAYS = 365


def compose_retention_policy() -> RetentionPolicy:
    """Build the sampling/redaction policy the operator configured via env."""
    sample_rate = _clamped_float(os.environ.get(SAMPLE_RATE_ENV), default=1.0)
    redact_fields = frozenset(
        name.strip() for name in os.environ.get(REDACT_FIELDS_ENV, "").split(",") if name.strip()
    )
    return RetentionPolicy(sample_rate=sample_rate, redact_fields=redact_fields)


def compose_retention_days() -> tuple[int, int]:
    """(raw_days, rollup_days) the operator configured via env, clamped to run_retention's bounds."""
    raw_days = _clamped_int(os.environ.get(RAW_DAYS_ENV), default=DEFAULT_RAW_DAYS, low=1, high=90)
    rollup_days = _clamped_int(os.environ.get(ROLLUP_DAYS_ENV), default=DEFAULT_ROLLUP_DAYS, low=30, high=3650)
    return raw_days, rollup_days


def _clamped_float(raw: str | None, *, default: float) -> float:
    if raw is None:
        return default
    try:
        value = float(raw)
    except ValueError:
        return default
    return max(0.0, min(1.0, value))


def _clamped_int(raw: str | None, *, default: int, low: int, high: int) -> int:
    if raw is None:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(low, min(high, value))


__all__ = [
    "SAMPLE_RATE_ENV", "REDACT_FIELDS_ENV", "RAW_DAYS_ENV", "ROLLUP_DAYS_ENV",
    "compose_retention_policy", "compose_retention_days",
]
