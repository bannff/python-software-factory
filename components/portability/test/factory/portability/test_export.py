"""portability.runtime.export — reads through the invoker seam, builds a
secret-free bundle. Row 54 Portability."""
from __future__ import annotations

import pytest
from factory.mcp_utils.interface import get_service, reset_envelope, set_envelope, set_service

from factory.portability.runtime.export import ExportError, build_bundle

MEMORY_ROWS = [
    {"id": "m1", "content": "the sky is blue", "memory_type": "semantic", "tags": ["fact"]},
    {"id": "m2", "content": "user prefers dark mode", "memory_type": "episodic", "tags": []},
]
LESSON_ROWS = [
    {"id": "l1", "rule": "always ask before deleting", "category": "safety", "negative": "delete silently"},
]
SCHEDULE_ROWS = [
    {"id": "s1", "name": "daily check", "message": "check status", "schedule_kind": "cron",
     "cron_expr": "0 9 * * *", "agent_id": "default"},
]
KB_ROWS = [{"id": "d1", "source": "notes.md", "content": "project notes here"}]
PREFS = {"theme": "dark", "density": "comfortable", "language": "en", "terminal_font_size": 14}


def _ok(data: dict) -> dict:
    return {"ok": True, "result": {"structured_content": {"ok": True, "data": data}}}


def _invoker_for(routes: dict[tuple[str, str], dict]):
    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            key = (target["brick_name"], target["tool_name"])
            assert key in routes, f"unexpected call: {key}"
            return _ok(routes[key])
        return invoke
    return factory


_DEFAULT_ROUTES = {
    ("memory", "memory_list"): {"memories": MEMORY_ROWS},
    ("kb", "kb_list_documents"): {"documents": KB_ROWS},
    ("lessons", "lessons_list"): {"lessons": LESSON_ROWS},
    ("scheduler", "scheduler_list"): {"schedules": SCHEDULE_ROWS},
    ("ui", "ui_get_display_preferences"): PREFS,
}


@pytest.fixture(autouse=True)
def _restore_state():
    previous_invoker = get_service("tool_invoker_for_caller")
    yield
    set_service("tool_invoker_for_caller", previous_invoker)


def _with_envelope(routes: dict, fn):
    set_service("tool_invoker_for_caller", _invoker_for(routes))
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        return fn()
    finally:
        reset_envelope(token)


def test_builds_a_bundle_with_every_kind_by_default():
    bundle = _with_envelope(_DEFAULT_ROUTES, lambda: build_bundle())
    assert bundle["bundle_version"] == 1
    assert bundle["adapter"] == "companion-x-v1"
    assert set(bundle["kinds"]) == {"memory", "kb", "lessons", "schedules", "preferences"}
    assert bundle["kinds"]["memory"]["count"] == 2
    assert bundle["kinds"]["lessons"]["count"] == 1
    assert bundle["kinds"]["schedules"]["count"] == 1
    assert bundle["kinds"]["kb"]["count"] == 1
    assert bundle["kinds"]["preferences"]["count"] == 1
    assert bundle["content_digest"].startswith("sha256:")


def test_selecting_specific_kinds_only_reads_those():
    routes = {("memory", "memory_list"): {"memories": MEMORY_ROWS}}
    bundle = _with_envelope(routes, lambda: build_bundle(("memory",)))
    assert set(bundle["kinds"]) == {"memory"}


def test_exported_schedules_are_always_paused():
    bundle = _with_envelope(_DEFAULT_ROUTES, lambda: build_bundle(("schedules",)))
    record = bundle["kinds"]["schedules"]["records"][0]
    assert record["paused"] is True


def test_record_identity_is_deterministic_across_calls():
    b1 = _with_envelope(_DEFAULT_ROUTES, lambda: build_bundle(("memory",)))
    b2 = _with_envelope(_DEFAULT_ROUTES, lambda: build_bundle(("memory",)))
    ids1 = sorted(r["identity"] for r in b1["kinds"]["memory"]["records"])
    ids2 = sorted(r["identity"] for r in b2["kinds"]["memory"]["records"])
    assert ids1 == ids2 and all(len(i) == 64 for i in ids1)


def test_missing_owner_context_raises_typed_error():
    set_service("tool_invoker_for_caller", _invoker_for(_DEFAULT_ROUTES))
    with pytest.raises(ExportError, match="portability_owner_context_required"):
        build_bundle()


def test_missing_invoker_raises_typed_error():
    set_service("tool_invoker_for_caller", None)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        with pytest.raises(ExportError, match="portability_runtime_unavailable"):
            build_bundle(("memory",))
    finally:
        reset_envelope(token)


def test_upstream_transport_failure_raises_typed_error():
    def factory(caller: str):
        return lambda *a, **k: {"ok": False}
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        with pytest.raises(ExportError, match="portability_memory_transport_failed"):
            build_bundle(("memory",))
    finally:
        reset_envelope(token)


def test_lessons_read_respects_the_real_lessons_list_limit_cap():
    """Regression for a real live bug: lessons_list's own ListLessonsInput
    caps `limit` at 1000 (unlike memory_list, uncapped, or kb_list_documents,
    capped at 10_000) — a blanket 10_000 for every kind's read call made
    lessons export fail validation on every real invocation. Validates the
    ACTUAL exported limit against the real contract, not a permissive mock
    that would never have caught this."""
    from factory.lessons.mcp.contracts import ListLessonsInput

    captured: dict[str, object] = {}

    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            if target == {"brick_name": "lessons", "tool_name": "lessons_list"}:
                captured["limit"] = arguments.get("limit")
                # exercise the REAL contract's own validation, not a stub
                ListLessonsInput.model_validate(arguments)
            return {"ok": True, "result": {"structured_content": {"ok": True, "data": {"lessons": []}}}}
        return invoke

    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        build_bundle(("lessons",))  # must not raise — proves the real cap is honored
    finally:
        reset_envelope(token)
    assert captured["limit"] is not None
    assert captured["limit"] <= 1000
