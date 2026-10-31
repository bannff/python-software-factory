"""migration.runtime.parsers.bundle — companion-x-v1 bundle records into
migration's own SafeMemory/SafeLesson/SafeSchedule (reused, not re-derived).
"""
from __future__ import annotations

from factory.migration.runtime.parsers.bundle import (
    bundle_kinds, parse_bundle_kind, unsupported_bundle_kinds,
)
from factory.migration.runtime.source_models import SafeLesson, SafeMemory, SafeSchedule

BUNDLE = {
    "kinds": {
        "memory": {"records": [
            {"identity": "m1", "content": "the sky is blue", "kind": "semantic", "tags": ["fact"]},
            {"identity": "m1", "content": "duplicate", "kind": "semantic", "tags": []},
            {"identity": "m2", "content": "", "kind": "semantic", "tags": []},  # empty -> malformed
            "not a dict",
        ]},
        "lessons": {"records": [
            {"identity": "l1", "rule": "always ask", "category": "safety", "negative": "never ask"},
        ]},
        "schedules": {"records": [
            {"identity": "s1", "name": "daily", "schedule_kind": "cron", "cron_expr": "0 9 * * *"},
        ]},
        "kb": {"records": [{"identity": "d1", "source": "notes.md", "content": "notes"}]},
        "preferences": {"records": [{"identity": "p1", "theme": "dark"}]},
    },
}


def test_bundle_kinds_lists_every_kind_present():
    assert set(bundle_kinds(BUNDLE)) == {"memory", "lessons", "schedules", "kb", "preferences"}


def test_unsupported_bundle_kinds_flags_kb_and_preferences():
    assert set(unsupported_bundle_kinds(BUNDLE)) == {"kb", "preferences"}


def test_parses_memory_records_and_diagnoses_the_rest():
    records, report = parse_bundle_kind(BUNDLE, "memory")
    assert len(records) == 1
    assert isinstance(records[0], SafeMemory)
    assert records[0].content == "the sky is blue"
    assert report.found == 4
    assert report.eligible == 1
    assert report.excluded == 3  # duplicate identity, empty content, non-dict


def test_parses_lessons_records():
    records, report = parse_bundle_kind(BUNDLE, "lessons")
    assert len(records) == 1
    assert isinstance(records[0], SafeLesson)
    assert records[0].rule == "always ask"
    assert records[0].negative == "never ask"


def test_parses_schedule_records_always_paused():
    records, report = parse_bundle_kind(BUNDLE, "schedules")
    assert len(records) == 1
    assert isinstance(records[0], SafeSchedule)
    assert records[0].paused is True
    assert records[0].schedule_kind == "cron"


def test_missing_kind_block_returns_empty():
    records, report = parse_bundle_kind({"kinds": {}}, "memory")
    assert records == []
    assert report.found == 0
