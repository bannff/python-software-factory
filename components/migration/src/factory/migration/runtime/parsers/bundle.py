"""Parse a staged ``companion-x-v1`` bundle's per-kind records into
migration's own strict source models (``SafeMemory``/``SafeLesson``/
``SafeSchedule``) — reused wholesale, not re-derived, so the existing
apply/target-preparation engine needs zero changes to accept them.

Kinds `kb` and `preferences` are NOT yet handled here (disclosed gap): no
``kb_import_record`` / preferences-import target tool exists yet, so
importing those kinds would have nowhere safe to write. `bundle_kinds()`
reports every kind the bundle CONTAINS regardless, so a caller can see
what's present even before all of it is importable.
"""
from __future__ import annotations

from typing import Any

from ..source_models import (
    Diagnostic, KindReport, ReasonCode, SafeLesson, SafeMemory, SafeSchedule,
    SourceKind, identity_of,
)
from . import build_report, malformed

_KIND_FOR_BUNDLE_KEY = {
    "memory": SourceKind.MEMORY, "lessons": SourceKind.LESSONS,
    "schedules": SourceKind.SCHEDULES,
}
_IMPORTABLE_BUNDLE_KEYS = frozenset(_KIND_FOR_BUNDLE_KEY)


def bundle_kinds(bundle: dict[str, Any]) -> tuple[str, ...]:
    """Every kind key present in the bundle, importable or not."""
    kinds = bundle.get("kinds", {})
    return tuple(kinds) if isinstance(kinds, dict) else ()


def unsupported_bundle_kinds(bundle: dict[str, Any]) -> tuple[str, ...]:
    """Kinds present in the bundle with no import target yet (disclosed,
    not silently dropped) — a caller can surface these to the owner."""
    return tuple(k for k in bundle_kinds(bundle) if k not in _IMPORTABLE_BUNDLE_KEYS)


def _memory_from(item: dict[str, Any]) -> SafeMemory | None:
    content = item.get("content")
    if not isinstance(content, str) or not content.strip():
        return None
    kind = item.get("kind")
    try:
        return SafeMemory(
            kind=kind if kind in ("semantic", "episodic") else "semantic",
            identity=identity_of("bundle-memory", str(item.get("identity", content))),
            key=item.get("key"), content=content,
            tags=tuple(str(t) for t in item.get("tags", []))[:64],
        )
    except (ValueError, TypeError):
        return None


def _lesson_from(item: dict[str, Any]) -> SafeLesson | None:
    rule = item.get("rule")
    if not isinstance(rule, str) or not rule.strip():
        return None
    try:
        return SafeLesson(
            identity=identity_of("bundle-lessons", str(item.get("identity", rule))),
            rule=rule, category=str(item.get("category", ""))[:64],
            negative=item.get("negative") if isinstance(item.get("negative"), str) else None,
            repo_scope=str(item.get("repo_scope", ""))[:256], origin="jsonl",
        )
    except (ValueError, TypeError):
        return None


def _schedule_from(item: dict[str, Any]) -> SafeSchedule | None:
    name = item.get("name")
    kind = item.get("schedule_kind")
    if not isinstance(name, str) or not name.strip() or kind not in ("every", "at", "cron"):
        return None
    try:
        return SafeSchedule(
            identity=identity_of("bundle-schedules", str(item.get("identity", name))),
            name=name[:200], message=str(item.get("message", "")),
            schedule_kind=kind, every_secs=item.get("every_secs"),
            at_ts=item.get("at_ts"), cron_expr=item.get("cron_expr"),
            timezone=str(item.get("timezone", ""))[:64],
            agent_id=str(item.get("agent_id", ""))[:128],
            model=str(item.get("model", ""))[:128], paused=True,
        )
    except (ValueError, TypeError):
        return None


_PARSER_FOR = {"memory": _memory_from, "lessons": _lesson_from, "schedules": _schedule_from}


def parse_bundle_kind(bundle: dict[str, Any], bundle_key: str):
    """Parse one importable kind's records into (records, KindReport)."""
    kind = _KIND_FOR_BUNDLE_KEY[bundle_key]
    block = bundle.get("kinds", {}).get(bundle_key, {})
    raw_records = block.get("records", []) if isinstance(block, dict) else []
    parser = _PARSER_FOR[bundle_key]
    records, diags, seen = [], [], set()
    for item in raw_records:
        if not isinstance(item, dict):
            diags.append(malformed(kind, "not_an_object"))
            continue
        parsed = parser(item)
        if parsed is None:
            diags.append(malformed(kind, "invalid_record"))
            continue
        if parsed.identity in seen:
            diags.append(Diagnostic(kind=kind, reason=ReasonCode.DUPLICATE, identity=parsed.identity))
            continue
        seen.add(parsed.identity)
        records.append(parsed)
    identities = [r.identity for r in records]
    return records, build_report(kind, len(raw_records), identities, diags)


__all__ = [
    "bundle_kinds", "parse_bundle_kind", "unsupported_bundle_kinds",
]
