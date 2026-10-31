"""Parse KiroCrew schedules from ``crons.json`` or ``cron/jobs.json`` (v2).

Only schedule-defining safe fields are read. Secret (``env``/``secret_env*``),
direct-execution (``script``/``command``), delivery-identity (``channel``/
``thread_ts``/``created_by``/``session_key``), and runtime result/error/dedupe
fields are NEVER read. Every imported schedule is marked ``paused``. Unknown
top-level versions fail the kind; malformed jobs are excluded per-record.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from ..source_models import (
    MAX_TEXT_CHARS, SUPPORTED_CRON_VERSIONS, Diagnostic, KindReport,
    ReasonCode, SafeSchedule, SourceKind, identity_of,
)
from . import build_report, malformed

_KIND = SourceKind.SCHEDULES
# Fields that must never be surfaced even if present in a job object.
_FORBIDDEN = frozenset({
    "env", "script", "command", "channel", "thread_ts", "created_by",
    "session_key", "last_result", "last_error", "last_status", "last_run_ts",
})


def _schedule_fields(sched: Any) -> tuple[str, int | None, float | None, str | None] | None:
    if not isinstance(sched, dict):
        return None
    kind = sched.get("kind")
    if kind not in ("every", "at", "cron"):
        return None
    every = sched.get("every_secs")
    at = sched.get("at_ts")
    expr = sched.get("cron_expr")
    if kind == "every" and not isinstance(every, int):
        return None
    if kind == "at" and not isinstance(at, (int, float)):
        return None
    if kind == "cron" and (not isinstance(expr, str) or not expr.strip()):
        return None
    return (
        kind,
        int(every) if kind == "every" else None,
        float(at) if kind == "at" else None,
        expr.strip()[:128] if kind == "cron" and isinstance(expr, str) else None,
    )


def _schedule_from(obj: Any) -> SafeSchedule | None:
    if not isinstance(obj, dict):
        return None
    name = obj.get("name")
    if not isinstance(name, str) or not name.strip() or len(name) > 200:
        return None
    message = obj.get("message")
    message = message if isinstance(message, str) and len(message) <= MAX_TEXT_CHARS else ""
    fields = _schedule_fields(obj.get("schedule"))
    if fields is None:
        return None
    kind, every, at, expr = fields
    identity_key = f"{name.strip()}|{kind}|{every}|{at}|{expr}"
    try:
        return SafeSchedule(
            identity=identity_of("cron", identity_key),
            name=name.strip(),
            message=message,
            schedule_kind=kind,  # type: ignore[arg-type]
            every_secs=every,
            at_ts=at,
            cron_expr=expr,
            timezone=str(obj.get("timezone") or "")[:64],
            skip_dates=tuple(v for v in (obj.get("skip_dates") or ())
                             if isinstance(v, str))[:366],
            strict_schedule=bool(obj.get("strict_schedule", False)),
            approval_mode="",
            agent_id=str(obj.get("agent_id") or "")[:128],
            model=str(obj.get("model") or "")[:128],
            paused=True,
        )
    except ValidationError:
        return None


def _load(snapshot_dir: Path) -> tuple[Any, str] | None:
    for rel in ("crons.json", "cron/jobs.json"):
        path = snapshot_dir / rel
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8")), rel
            except ValueError:
                return None, rel
    return None


def parse_schedules(snapshot_dir: Path) -> tuple[list[SafeSchedule], KindReport]:
    loaded = _load(Path(snapshot_dir))
    if loaded is None:
        return [], build_report(_KIND, 0, [], [])
    data, _rel = loaded
    if data is None:
        return [], build_report(_KIND, 0, [], [malformed(_KIND, "invalid json")])
    version = data.get("version", 2) if isinstance(data, dict) else None
    if not isinstance(version, int) or version not in SUPPORTED_CRON_VERSIONS:
        return [], build_report(
            _KIND, 0, [], [Diagnostic(kind=_KIND, reason=ReasonCode.UNKNOWN_VERSION, detail=f"v{version}")])
    jobs = data.get("jobs", []) if isinstance(data, dict) else []
    if not isinstance(jobs, list):
        jobs = []
    records: list[SafeSchedule] = []
    diags: list[Diagnostic] = []
    seen: set[str] = set()
    for job in jobs:
        sched = _schedule_from(job)
        if sched is None:
            diags.append(malformed(_KIND, "job"))
            continue
        if sched.identity in seen:
            diags.append(Diagnostic(kind=_KIND, reason=ReasonCode.DUPLICATE, identity=sched.identity))
            continue
        seen.add(sched.identity)
        records.append(sched)
    identities = [r.identity for r in records]
    return records, build_report(_KIND, len(jobs), identities, diags)


__all__ = ["parse_schedules", "_FORBIDDEN"]
