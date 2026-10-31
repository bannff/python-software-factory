"""Tests for schedules and markdown parsers (kirocrew-v1)."""
from __future__ import annotations

import json
from pathlib import Path

from factory.migration.runtime.parsers.schedules import _FORBIDDEN, parse_schedules
from factory.migration.runtime.parsers.markdown import parse_markdown
from factory.migration.runtime.source_models import ReasonCode, SafeSchedule


def _job(**over):
    base = {
        "id": "j1", "name": "nightly", "message": "run checks",
        "schedule": {"kind": "every", "every_secs": 300},
        "channel": "C123", "created_by": "U9",
        "env": {"SECRET_TOKEN": "abc"}, "secret_env": {"K": "v"},
        "script": "~/x.py:go", "command": "rm -rf /",
        "last_status": "error", "last_error": "boom", "last_result": "nope",
        "approval_mode": "auto", "timezone": "UTC", "strict_schedule": True,
        "skip_dates": ["2026-12-25"],
        "agent_id": "a1", "model": "openrouter/x",
    }
    base.update(over)
    return base


def _write(tmp_path: Path, data) -> None:
    (tmp_path / "crons.json").write_text(json.dumps(data))


def test_schedule_safe_fields_only(tmp_path):
    _write(tmp_path, {"version": 2, "jobs": [_job()]})
    records, report = parse_schedules(tmp_path)
    assert len(records) == 1
    s = records[0]
    assert s.name == "nightly" and s.schedule_kind == "every" and s.every_secs == 300
    assert s.approval_mode == "" and s.timezone == "UTC" and s.model == "openrouter/x"
    assert s.skip_dates == ("2026-12-25",)


def test_safe_schedule_model_has_no_forbidden_fields():
    assert _FORBIDDEN & set(SafeSchedule.model_fields) == set()


def test_schedule_always_paused(tmp_path):
    _write(tmp_path, {"version": 2, "jobs": [_job(enabled=True)]})
    records, _ = parse_schedules(tmp_path)
    assert records[0].paused is True


def test_schedule_unknown_version_fails(tmp_path):
    _write(tmp_path, {"version": 99, "jobs": [_job()]})
    records, report = parse_schedules(tmp_path)
    assert records == []
    assert ReasonCode.UNKNOWN_VERSION in {d.reason for d in report.diagnostics}


def test_schedule_missing_version_defaults_v2(tmp_path):
    _write(tmp_path, {"jobs": [_job()]})
    records, _ = parse_schedules(tmp_path)
    assert len(records) == 1


def test_schedule_malformed_job_excluded(tmp_path):
    _write(tmp_path, {"version": 2, "jobs": [
        _job(),
        {"name": "bad", "schedule": {"kind": "every"}},  # missing every_secs
        {"name": "", "schedule": {"kind": "cron", "cron_expr": "* * * * *"}},  # blank name
    ]})
    records, report = parse_schedules(tmp_path)
    assert len(records) == 1
    assert report.found == 3
    assert ReasonCode.MALFORMED in {d.reason for d in report.diagnostics}


def test_schedule_every_below_floor_excluded(tmp_path):
    _write(tmp_path, {"version": 2, "jobs": [_job(schedule={"kind": "every", "every_secs": 5})]})
    records, _ = parse_schedules(tmp_path)
    # every_secs=5 is below the SafeSchedule ge=60 floor -> not a valid safe record
    assert records == []


def test_schedule_cron_and_at_shapes(tmp_path):
    _write(tmp_path, {"version": 2, "jobs": [
        _job(name="c", schedule={"kind": "cron", "cron_expr": "0 9 * * 1-5"}),
        _job(name="o", schedule={"kind": "at", "at_ts": 1893456000.0}),
    ]})
    records, _ = parse_schedules(tmp_path)
    kinds = {r.schedule_kind for r in records}
    assert kinds == {"cron", "at"}


def test_markdown_parses_supported_docs(tmp_path):
    mem = tmp_path / "workspace" / "memory" / "history"
    mem.mkdir(parents=True)
    (tmp_path / "workspace" / "memory" / "preferences.md").write_text("# prefs\n")
    (tmp_path / "workspace" / "memory" / "projects.md").write_text("# projects\n")
    (mem / "2026-01-01.md").write_text("history entry\n")
    records, report = parse_markdown(tmp_path)
    docs = {r.doc for r in records}
    assert docs == {"preferences", "projects", "history"}
    assert report.eligible == 3


def test_markdown_empty_file_excluded(tmp_path):
    (tmp_path / "workspace" / "memory").mkdir(parents=True)
    (tmp_path / "workspace" / "memory" / "preferences.md").write_text("   \n")
    (tmp_path / "workspace" / "memory" / "projects.md").write_text("real\n")
    records, report = parse_markdown(tmp_path)
    assert {r.doc for r in records} == {"projects"}
    assert ReasonCode.EMPTY in {d.reason for d in report.diagnostics}
