"""Unit tests for the closed target union, redaction, and record guarantees."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from factory.notification.runtime.inbox_models import NotificationRecord, Priority
from factory.notification.runtime.inbox_redact import (
    MAX_BODY_CHARS, MAX_TITLE_CHARS, redact,
)
from factory.notification.runtime.inbox_targets import (
    ArtifactTarget, NotificationTarget, SessionTarget, build_target, target_id,
    target_kind,
)
from pydantic import TypeAdapter

_ADAPTER = TypeAdapter(NotificationTarget)
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _record(**over) -> NotificationRecord:
    base = dict(
        tenant_id="tenant-1", owner_id="owner-1", notification_id="ntf-1",
        kind="schedule_fired", title="Your schedule fired", body="all good",
        priority=Priority.DEFAULT, target=SessionTarget(session_id="sess-1"),
        dedupe_key="dk-1", created_at=_NOW,
    )
    base.update(over)
    return NotificationRecord(**base)


def test_every_target_variant_roundtrips() -> None:
    pairs = [("session", "s1"), ("workflow_run", "sha256:abc123"),
             ("schedule", "sch1"), ("artifact", "cr-queue"), ("crew", "crew1"),
             ("lesson", "les1"), ("canvas", "security")]
    for kind, ident in pairs:
        t = build_target(kind, ident)
        assert target_kind(t) == kind and target_id(t) == ident


def test_unknown_target_kind_rejected() -> None:
    with pytest.raises(ValueError):
        build_target("mystery", "x")
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python({"kind": "mystery", "id": "x"})


@pytest.mark.parametrize("bad", [
    "http://evil.com/x", "https://a.b/c", "/etc/passwd", "../escape",
    "file:///x", "javascript:alert(1)", "a b", "has/slash",
])
def test_external_url_and_path_ids_rejected(bad: str) -> None:
    with pytest.raises(ValidationError):
        SessionTarget(session_id=bad)
    with pytest.raises(ValidationError):
        ArtifactTarget(slug=bad)


def test_redaction_strips_credentials_and_pii() -> None:
    secret = "token=AKIAABCDEFGHIJKLMNOP email a@b.com call 555-123-4567"
    out = redact(secret, limit=MAX_BODY_CHARS)
    assert "AKIA" not in out and "a@b.com" not in out
    assert "[redacted]" in out


def test_redaction_is_idempotent_and_bounded() -> None:
    once = redact("sk-proj_" + "a" * 40 + " " + "x" * 5000, limit=MAX_BODY_CHARS)
    assert redact(once, limit=MAX_BODY_CHARS) == once
    assert len(once) <= MAX_BODY_CHARS


def test_record_redacts_title_and_body_at_construction() -> None:
    r = _record(title="key sk-live_" + "b" * 30, body="ssn 123-45-6789")
    assert "sk-live_" not in r.title
    assert "123-45-6789" not in r.body
    assert len(r.title) <= MAX_TITLE_CHARS


def test_content_digest_excludes_volatile_fields() -> None:
    a = _record(notification_id="ntf-1", revision=1, read_at=None)
    b = _record(notification_id="ntf-9", revision=4,
                read_at=datetime(2026, 2, 2, tzinfo=timezone.utc))
    assert a.content_digest == b.content_digest
    c = _record(title="different title")
    assert c.content_digest != a.content_digest


def test_invalid_identifiers_rejected() -> None:
    with pytest.raises(ValidationError):
        _record(notification_id="bad id")
    with pytest.raises(ValidationError):
        _record(dedupe_key="has/slash")
    with pytest.raises(ValidationError):
        _record(kind="Not-A-Kind")
