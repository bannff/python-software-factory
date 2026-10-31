"""Owner notification preference persistence, MCP, and delivery-seam tests."""
from __future__ import annotations

import asyncio

from hypothesis import given, strategies as st

from factory.mcp_utils.interface import ToolCatalog, reset_envelope, set_envelope
from factory.notification.mcp import prefs_deterministic, prefs_operational
from factory.notification.runtime.adapters.prefs_store_sql import SqlPreferencesStore
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_models import Priority, RevisionConflictError
from factory.notification.runtime.inbox_projection import material_digest, project_notification
from factory.notification.runtime.prefs_models import NotificationPreferences

_T, _O, _K = "tenant-1", "owner-1", "scheduler_auto_paused"


def _prefs(**over) -> NotificationPreferences:
    values = dict(tenant_id=_T, owner_id=_O, global_muted=False,
                  muted_kinds=frozenset(), priority_overrides={}, revision=1)
    values.update(over)
    return NotificationPreferences(**values)


def _projection() -> dict:
    values = dict(event_type="scheduler.schedule.auto_paused", subject_id="nightly",
                  revision=5, dedupe_key="auto-pause:nightly:5", priority="critical",
                  title="Schedule auto-paused", body="Five failures")
    return dict(tenant_id=_T, owner_id=_O, payload_digest=material_digest(**values),
                **values)


def _tools(runtime: NotificationRuntime) -> dict:
    catalog = ToolCatalog("test")
    prefs_deterministic.register(catalog, runtime)
    prefs_operational.register(catalog, runtime)
    return {tool.name: tool for tool in asyncio.run(catalog.list_tools())}


def _call(tool, envelope, **kwargs):
    token = set_envelope(envelope) if envelope is not None else None
    try:
        return tool.fn(**kwargs)
    finally:
        reset_envelope(token)


def test_store_default_cas_restart_and_json_round_trip(tmp_path) -> None:
    db = str(tmp_path / "prefs.db")
    store = SqlPreferencesStore(db_path=db)
    assert store.get(_T, _O) == _prefs()
    saved = store.put(_prefs(
        global_muted=True, muted_kinds=frozenset({_K}),
        priority_overrides={_K: Priority.PASSIVE}), expected_revision=1)
    assert saved.revision == 2 and saved.global_muted
    assert saved.muted_kinds == frozenset({_K})
    assert saved.priority_overrides == {_K: Priority.PASSIVE}
    assert SqlPreferencesStore(db_path=db).get(_T, _O) == saved
    try:
        store.put(_prefs(), expected_revision=1)
    except RevisionConflictError:
        pass
    else:
        raise AssertionError("stale preference write must conflict")


def test_mute_persists_record_without_delivery(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    asyncio.run(runtime.initialize())
    runtime.prefs_update(_T, _O, global_muted=False,
                         muted_kinds=frozenset({_K}), priority_overrides={},
                         expected_revision=1)
    sends = []

    async def send(**kwargs):
        sends.append(kwargs)
        return {"ok": True, "status": "sent"}

    runtime.send_notification = send  # type: ignore[method-assign]
    outcome = asyncio.run(project_notification(runtime, **_projection()))
    assert outcome.status == "created" and outcome.delivery == "skipped_muted"
    assert runtime.inbox_get(_T, _O, outcome.notification_id).priority is Priority.CRITICAL
    assert sends == []


def test_override_is_delivery_only_and_pref_change_replays(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    asyncio.run(runtime.initialize())
    runtime.prefs_update(_T, _O, global_muted=False, muted_kinds=frozenset(),
                         priority_overrides={_K: Priority.PASSIVE},
                         expected_revision=1)
    sends = []

    async def send(**kwargs):
        sends.append(kwargs)
        return {"ok": True, "status": "sent"}

    runtime.send_notification = send  # type: ignore[method-assign]
    first = asyncio.run(project_notification(runtime, **_projection()))
    stored = runtime.inbox_get(_T, _O, first.notification_id)
    assert sends[0]["priority"] == "low" and stored.priority is Priority.CRITICAL
    runtime.prefs_update(_T, _O, global_muted=True, muted_kinds=frozenset(),
                         priority_overrides={}, expected_revision=2)
    replay = asyncio.run(project_notification(runtime, **_projection()))
    assert replay.status == "replayed" and replay.delivery == "skipped"
    assert len(sends) == 1


def test_mcp_ambient_identity_read_update_and_conflict(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    tools = _tools(runtime)
    envelope = {"tenant_id": _T, "principal_id": _O}
    default = _call(tools["get_preferences"], envelope)
    assert default.ok and default.data.revision == 1
    saved = _call(tools["update_preferences"], envelope, global_muted=True,
                  muted_kinds=[_K], priority_overrides={_K: "default"},
                  expected_revision=1)
    assert saved.ok and saved.data.revision == 2
    stale = _call(tools["update_preferences"], envelope, global_muted=False,
                  muted_kinds=[], priority_overrides={}, expected_revision=1)
    assert not stale.ok and stale.error == "notification_revision_conflict"
    missing = _call(tools["get_preferences"], None)
    assert not missing.ok and missing.error == "notification_inbox_unavailable"


@given(global_muted=st.booleans(), muted=st.sets(st.sampled_from([_K, "other"])))
def test_effective_delivery_is_deterministic(global_muted, muted) -> None:
    prefs = _prefs(global_muted=global_muted, muted_kinds=frozenset(muted),
                   priority_overrides={_K: Priority.PASSIVE})
    expected = not global_muted and _K not in muted
    assert prefs.effective_delivery(_K, Priority.CRITICAL) == (
        expected, Priority.PASSIVE)
    assert prefs.effective_delivery(_K, Priority.CRITICAL) == (
        expected, Priority.PASSIVE)
    assert prefs.effective_delivery("unconfigured", Priority.DEFAULT) == (
        not global_muted, Priority.DEFAULT)
