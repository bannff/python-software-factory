"""Tests for migration source models, redaction, and deterministic digests."""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from pydantic import ValidationError

from factory.migration.runtime.parsers import kind_digest
from factory.migration.runtime.source_models import (
    MAX_SAMPLE_CHARS, SafeSchedule, SourceKind, identity_of, redact,
)


def test_identity_is_stable_64hex():
    a = identity_of("lesson", "always test")
    b = identity_of("lesson", "always test")
    assert a == b and len(a) == 64 and all(c in "0123456789abcdef" for c in a)
    assert identity_of("lesson", "always test") != identity_of("cron", "always test")


def test_redact_strips_credential_shapes_and_bounds_length():
    secret = "password=hunter2 AKIA1234567890ABCDEF token: abcdef0123456789abcdef0123456789"
    out = redact(secret)
    assert "hunter2" not in out
    assert "AKIA1234567890ABCDEF" not in out
    assert "abcdef0123456789abcdef0123456789" not in out
    assert "[redacted]" in out


def test_redact_truncates():
    out = redact("word " * 500)
    assert len(out) <= MAX_SAMPLE_CHARS + 1


def test_safe_schedule_is_frozen_and_forbids_extra():
    sched = SafeSchedule(
        identity=identity_of("cron", "x"), name="job", schedule_kind="every",
        every_secs=300)
    with pytest.raises(ValidationError):
        sched.name = "other"  # type: ignore[misc]
    with pytest.raises(ValidationError):
        SafeSchedule(
            identity=identity_of("cron", "x"), name="job",
            schedule_kind="every", every_secs=300, command="rm -rf /")  # extra field


def test_safe_schedule_paused_is_always_true():
    with pytest.raises(ValidationError):
        SafeSchedule(
            identity=identity_of("cron", "x"), name="job",
            schedule_kind="every", every_secs=300, paused=False)  # type: ignore[arg-type]


def test_every_secs_floor_enforced():
    with pytest.raises(ValidationError):
        SafeSchedule(
            identity=identity_of("cron", "x"), name="job",
            schedule_kind="every", every_secs=30)


@given(ids=st.lists(st.text(min_size=1, max_size=20), max_size=30))
@settings(max_examples=50)
def test_kind_digest_is_order_independent_and_deterministic(ids):
    identities = [identity_of("t", i) for i in ids]
    shuffled = list(reversed(identities))
    assert kind_digest(SourceKind.MEMORY, identities) == kind_digest(SourceKind.MEMORY, shuffled)


@given(ids=st.lists(st.text(min_size=1, max_size=8), min_size=1, max_size=10, unique=True))
@settings(max_examples=50)
def test_kind_digest_changes_with_kind(ids):
    identities = [identity_of("t", i) for i in ids]
    assert kind_digest(SourceKind.MEMORY, identities) != kind_digest(SourceKind.LESSONS, identities)


def test_kind_report_caps_diagnostics_but_keeps_total_count():
    from factory.migration.runtime.parsers import build_report
    from factory.migration.runtime.source_models import Diagnostic, MAX_DIAGNOSTICS, ReasonCode

    diagnostics = [
        Diagnostic(kind=SourceKind.MEMORY, reason=ReasonCode.MALFORMED)
        for _ in range(MAX_DIAGNOSTICS + 7)
    ]
    report = build_report(SourceKind.MEMORY, 0, [], diagnostics)
    assert len(report.diagnostics) == MAX_DIAGNOSTICS
    assert report.excluded == MAX_DIAGNOSTICS + 7
