"""Export runtime: reads owner-scoped content through the existing public
read tools of other bricks (never a direct import of their runtimes) and
materializes a secret-free, versioned bundle.

Structural exclusion is the primary secret guarantee: only public read
tools are called, and ``owner_secrets`` has no read/reveal tool anywhere in
the stack, so a secret value is unreachable by construction — this runtime
could not read one even if it tried. ``redaction.scrub``/``still_trips`` is
the secondary, defense-in-depth check applied to every string before it
enters a record.
"""
from __future__ import annotations

import asyncio
import json
from typing import Any

from factory.mcp_utils.interface import get_envelope, get_service

from .bundle_models import (
    BUNDLE_ADAPTER, BUNDLE_VERSION, EXPORT_KINDS, SafeKbRecord, SafeLessonRecord,
    SafeMemoryRecord, SafePreferencesRecord, SafeScheduleRecord, identity_of, sha256_hex,
)
from .redaction import scrub, still_trips


class ExportError(RuntimeError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def _authority() -> dict[str, Any]:
    envelope = get_envelope()
    if not isinstance(envelope, dict) or not envelope.get("tenant_id") or not envelope.get("principal_id"):
        raise ExportError("portability_owner_context_required")
    return envelope


def _invoke(brick: str, tool: str, arguments: dict[str, Any], envelope: dict[str, Any]) -> Any:
    factory = get_service("tool_invoker_for_caller")
    invoker = factory("portability") if callable(factory) else None
    if not callable(invoker):
        raise ExportError("portability_runtime_unavailable")
    raw = invoker(
        {"brick_name": brick, "tool_name": tool}, arguments=arguments,
        idempotency_key=None, envelope=envelope,
    )
    if not isinstance(raw, dict) or raw.get("ok") is not True:
        raise ExportError(f"portability_{brick}_transport_failed")
    structured = raw.get("result", {}).get("structured_content")
    if not isinstance(structured, dict) or structured.get("ok") is not True:
        raise ExportError(f"portability_{brick}_read_failed")
    return structured.get("data", {})


def _safe_string(namespace: str, value: str) -> tuple[str, bool]:
    """Scrub once; report whether the value must be rejected (still trips)."""
    scrubbed = scrub(value)
    return scrubbed, still_trips(scrubbed)


def _memory_records(envelope: dict[str, Any]) -> tuple[list[SafeMemoryRecord], int]:
    data = _invoke("memory", "memory_list", {"limit": 10_000}, envelope)
    rows, excluded = [], 0
    for item in data.get("memories", []):
        if not isinstance(item, dict):
            continue
        content, rejected = _safe_string("memory", str(item.get("content", "")))
        if rejected or not content.strip():
            excluded += 1
            continue
        key = item.get("id") or item.get("memory_id")
        rows.append(SafeMemoryRecord(
            kind=item.get("memory_type", "semantic") if item.get("memory_type") in ("semantic", "episodic") else "semantic",
            identity=identity_of("memory", str(key or content)),
            key=str(key) if key else None, content=content,
            tags=tuple(str(t) for t in item.get("tags", []))[:64],
        ))
    return rows, excluded


def _kb_records(envelope: dict[str, Any]) -> tuple[list[SafeKbRecord], int]:
    data = _invoke("kb", "kb_list_documents", {"limit": 10_000}, envelope)
    rows, excluded = [], 0
    for item in data.get("documents", []):
        if not isinstance(item, dict):
            continue
        content, rejected = _safe_string("kb", str(item.get("content", item.get("source", ""))))
        if rejected or not content.strip():
            excluded += 1
            continue
        rows.append(SafeKbRecord(
            identity=identity_of("kb", str(item.get("id", content))),
            source=str(item.get("source", ""))[:512], content=content,
        ))
    return rows, excluded


def _lesson_records(envelope: dict[str, Any]) -> tuple[list[SafeLessonRecord], int]:
    # lessons_list caps limit at 1000 (ListLessonsInput: le=1000) — unlike
    # memory_list (uncapped) and kb_list_documents (le=10_000). Passing this
    # brick's own real maximum, not a blanket 10_000, is what actually fixed
    # the live "portability_lessons_transport_failed" finding: it was a
    # mundane input-validation rejection, masked by a generic transport-error
    # code until the tool-layer error-swallowing fix (same cycle) surfaced
    # the real SchemaMigrationError underneath.
    data = _invoke("lessons", "lessons_list", {"limit": 1000}, envelope)
    rows, excluded = [], 0
    for item in data.get("lessons", []):
        if not isinstance(item, dict):
            continue
        rule, rejected = _safe_string("lessons", str(item.get("rule", "")))
        if rejected or not rule.strip():
            excluded += 1
            continue
        negative = item.get("negative")
        if isinstance(negative, str):
            negative, neg_rejected = _safe_string("lessons", negative)
            if neg_rejected:
                negative = None
        rows.append(SafeLessonRecord(
            identity=identity_of("lessons", str(item.get("id", rule))), rule=rule,
            category=str(item.get("category", ""))[:64],
            negative=negative if isinstance(negative, str) else None,
            repo_scope=str(item.get("repo_scope", ""))[:256],
        ))
    return rows, excluded


def _schedule_records(envelope: dict[str, Any]) -> tuple[list[SafeScheduleRecord], int]:
    data = _invoke("scheduler", "scheduler_list", {}, envelope)
    rows, excluded = [], 0
    for item in data.get("schedules", []):
        if not isinstance(item, dict):
            continue
        message, rejected = _safe_string("schedules", str(item.get("message", "")))
        if rejected:
            excluded += 1
            continue
        kind = item.get("schedule_kind", item.get("kind", "every"))
        rows.append(SafeScheduleRecord(
            identity=identity_of("schedules", str(item.get("id", item.get("name", "")))),
            name=str(item.get("name", ""))[:200] or "untitled", message=message,
            schedule_kind=kind if kind in ("every", "at", "cron") else "every",
            every_secs=item.get("every_secs"), at_ts=item.get("at_ts"),
            cron_expr=item.get("cron_expr"), timezone=str(item.get("timezone", ""))[:64],
            agent_id=str(item.get("agent_id", ""))[:128], model=str(item.get("model", ""))[:128],
        ))
    return rows, excluded


def _preferences_records(envelope: dict[str, Any]) -> tuple[list[SafePreferencesRecord], int]:
    data = _invoke("ui", "ui_get_display_preferences", {}, envelope)
    identity = identity_of("preferences", f"{envelope.get('tenant_id')}:{envelope.get('principal_id')}")
    record = SafePreferencesRecord(
        identity=identity, theme=str(data.get("theme", "system")),
        density=str(data.get("density", "comfortable")), language=str(data.get("language", "en")),
        terminal_font_size=int(data.get("terminal_font_size", 11)),
    )
    return [record], 0


_BUILDERS = {
    "memory": _memory_records, "kb": _kb_records, "lessons": _lesson_records,
    "schedules": _schedule_records, "preferences": _preferences_records,
}


def build_bundle(kinds: tuple[str, ...] | None = None) -> dict[str, Any]:
    """Read every requested kind and assemble the manifest dict. No file
    write happens here — callers decide preview (discard) vs export (write)."""
    envelope = _authority()
    selected = tuple(k for k in (kinds or EXPORT_KINDS) if k in _BUILDERS)
    kinds_block: dict[str, Any] = {}
    for kind in selected:
        records, excluded = _BUILDERS[kind](envelope)
        payload = [record.model_dump(mode="json") for record in records]
        digest = sha256_hex(json.dumps(payload, sort_keys=True))
        kinds_block[kind] = {
            "count": len(payload), "excluded": excluded, "digest": f"sha256:{digest}",
            "records": payload,
        }
    content_digest = sha256_hex(json.dumps(kinds_block, sort_keys=True))
    return {
        "bundle_version": BUNDLE_VERSION, "adapter": BUNDLE_ADAPTER,
        "producer": {"app": "companion-x", "kinds": list(selected)},
        "content_digest": f"sha256:{content_digest}", "kinds": kinds_block,
    }


async def build_bundle_async(kinds: tuple[str, ...] | None = None) -> dict[str, Any]:
    return await asyncio.to_thread(build_bundle, kinds)


__all__ = ["ExportError", "build_bundle", "build_bundle_async"]
