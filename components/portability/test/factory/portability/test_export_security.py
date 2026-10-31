"""portability.runtime.export — security guarantees (row 54 Portability,
design consult §5): secrets never survive into an export bundle, and the
export path never reaches an owner_secrets-shaped tool. Split from
test_export.py to stay under the 200-LOC file ceiling; reuses its fixtures.
"""
from __future__ import annotations

from factory.mcp_utils.interface import reset_envelope, set_envelope, set_service

from factory.portability.runtime.export import build_bundle

from .test_export import KB_ROWS, PREFS, SCHEDULE_ROWS, _DEFAULT_ROUTES, _ok, _with_envelope
from .test_export import _restore_state  # noqa: F401 -- autouse fixture


def test_export_bundle_excludes_secrets():
    """Plant credential-shaped strings in every kind's content; assert none
    survive into the bundle. Content with a secret shape is scrubbed
    in place (kept, redacted) — a record is only dropped outright if a
    secret pattern still trips AFTER scrubbing, which would indicate the
    scrub itself failed to fully remove it."""
    routes = {
        ("memory", "memory_list"): {"memories": [
            {"id": "m1", "content": "safe content", "memory_type": "semantic", "tags": []},
            {"id": "m2", "content": "AKIA1234567890ABCDEF is my key", "memory_type": "semantic", "tags": []},
        ]},
        ("kb", "kb_list_documents"): {"documents": KB_ROWS},
        ("lessons", "lessons_list"): {"lessons": [
            {"id": "l1", "rule": "safe rule", "category": "x"},
            {"id": "l2", "rule": "use bearer sk-abcdefghijklmnopqrstuvwxyz to auth", "category": "x"},
        ]},
        ("scheduler", "scheduler_list"): {"schedules": SCHEDULE_ROWS},
        ("ui", "ui_get_display_preferences"): PREFS,
    }
    bundle = _with_envelope(routes, lambda: build_bundle())
    raw = str(bundle)
    assert "AKIA1234567890ABCDEF" not in raw
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in raw
    # both records were KEPT (content, not deletion, is the redaction contract)
    # but the planted secret text is gone, replaced with the redaction marker
    assert bundle["kinds"]["memory"]["count"] == 2
    assert bundle["kinds"]["memory"]["excluded"] == 0
    assert "[redacted]" in bundle["kinds"]["memory"]["records"][1]["content"]
    assert bundle["kinds"]["lessons"]["count"] == 2
    assert "[redacted]" in bundle["kinds"]["lessons"]["records"][1]["rule"]
    # the genuinely safe records are untouched
    assert bundle["kinds"]["memory"]["records"][0]["content"] == "safe content"
    assert bundle["kinds"]["lessons"]["records"][0]["rule"] == "safe rule"


def test_a_record_that_still_trips_the_guard_after_scrubbing_is_rejected():
    """Force a pattern that the scrub step does not remove (an unhandled
    shape) to prove the reject-not-ship path is real, not dead code."""
    from factory.portability.runtime import export as export_module
    original_still_trips = export_module.still_trips
    try:
        # simulate a pattern that scrub can't fully clear, so the post-scrub
        # check is exercised for real rather than always seeing a clean string
        export_module.still_trips = lambda text: "UNREMOVABLE" in text
        routes = {
            ("memory", "memory_list"): {"memories": [
                {"id": "m1", "content": "safe", "memory_type": "semantic", "tags": []},
                {"id": "m2", "content": "UNREMOVABLE secret shape", "memory_type": "semantic", "tags": []},
            ]},
        }
        bundle = _with_envelope(routes, lambda: build_bundle(("memory",)))
        assert bundle["kinds"]["memory"]["count"] == 1
        assert bundle["kinds"]["memory"]["excluded"] == 1
        assert bundle["kinds"]["memory"]["records"][0]["content"] == "safe"
    finally:
        export_module.still_trips = original_still_trips


def test_export_bundle_never_reads_owner_secrets():
    """Structural guarantee: nothing in build_bundle ever calls a
    storage/owner_secrets tool — confirmed by asserting the invoker sees
    ONLY the five allowlisted read calls, never anything from `storage`."""
    calls: list[tuple[str, str]] = []

    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            calls.append((target["brick_name"], target["tool_name"]))
            key = (target["brick_name"], target["tool_name"])
            return _ok(_DEFAULT_ROUTES[key])
        return invoke
    set_service("tool_invoker_for_caller", factory)
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    try:
        build_bundle()
    finally:
        reset_envelope(token)
    assert all(brick != "storage" for brick, _ in calls)
    assert set(calls) == set(_DEFAULT_ROUTES.keys())
