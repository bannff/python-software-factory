"""Typed MCP boundary tests for the durable notification inbox tools.

Covers tool taxonomy + exact egress DTO shape, strict ingress rejection,
ambient-identity derivation (missing/foreign), list/get, stale revision CAS,
the mark-all count fence with no partial mutation, and content-free failures.
"""
from __future__ import annotations

import asyncio
import inspect
import json
from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from factory.mcp_utils.interface import ToolCatalog, reset_envelope, set_envelope
from factory.notification.mcp import inbox_deterministic, inbox_operational
from factory.notification.mcp.contracts.inbox_inputs import (
    InboxGetInput, InboxListInput, InboxMarkAllReadInput, InboxMarkReadInput,
)
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_models import (
    NotificationRecord, Priority,
)
from factory.notification.runtime.inbox_targets import SessionTarget

_T = "tenant-1"
_OWNER = "owner-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_ENVELOPE = {"tenant_id": _T, "principal_id": _OWNER}


def _rec(nid: str, dk: str, owner: str = _OWNER) -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="schedule_fired",
        title="hello", priority=Priority.DEFAULT,
        target=SessionTarget(session_id="s"), dedupe_key=dk, created_at=_NOW)


def _tools(runtime: NotificationRuntime) -> dict:
    catalog = ToolCatalog("test")
    inbox_deterministic.register(catalog, runtime)
    inbox_operational.register(catalog, runtime)
    return {tool.name: tool for tool in asyncio.run(catalog.list_tools())}


def _call(tool, envelope: dict | None, **kwargs):
    token = set_envelope(envelope) if envelope is not None else None
    try:
        return tool.fn(**kwargs)
    finally:
        reset_envelope(token)


def _runtime(tmp_path) -> NotificationRuntime:
    return NotificationRuntime(tmp_path)


def test_tool_taxonomy_and_exact_egress(tmp_path) -> None:
    tools = _tools(_runtime(tmp_path))
    assert tools["inbox_list"].fn._mcp_category == "deterministic"
    assert tools["inbox_get"].fn._mcp_category == "deterministic"
    assert tools["inbox_mark_read"].fn._mcp_category == "operational"
    assert tools["inbox_mark_all_read"].fn._mcp_category == "operational"
    for tool in tools.values():
        model = tool.fn._mcp_output_model
        assert model.__module__.startswith("factory.notification.mcp.contracts")
        assert str(inspect.signature(tool.fn).return_annotation) == f"ToolResult[{model.__name__}]"


def test_strict_ingress_rejects_bad_input() -> None:
    with pytest.raises(ValidationError):
        InboxListInput(limit=0)
    with pytest.raises(ValidationError):
        InboxListInput(limit=101)
    with pytest.raises(ValidationError):
        InboxListInput(offset=-1)
    with pytest.raises(ValidationError):
        InboxListInput(unread_only=True, unexpected=1)
    with pytest.raises(ValidationError):
        InboxGetInput(notification_id="bad id")
    with pytest.raises(ValidationError):
        InboxMarkReadInput(notification_id="n-1", expected_revision=0)
    with pytest.raises(ValidationError):
        InboxMarkAllReadInput(expected_unread_count=-1)


def test_missing_ambient_identity_is_content_free_failure(tmp_path) -> None:
    result = _call(_tools(_runtime(tmp_path))["inbox_list"], None)
    assert result.ok is False and result.error == "notification_inbox_unavailable"
    assert tmp_path.name not in json.dumps(result.model_dump())


def test_foreign_and_absent_get_are_opaque_not_found(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("n-1", "dk-1"))
    tools = _tools(runtime)
    foreign = _call(tools["inbox_get"], {"tenant_id": _T, "principal_id": "owner-2"},
                    notification_id="n-1")
    absent = _call(tools["inbox_get"], _ENVELOPE, notification_id="missing")
    assert foreign.ok is False and foreign.error == "notification_not_found"
    assert absent.ok is False and absent.error == "notification_not_found"


def test_list_and_get_happy_path(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("n-1", "dk-1"))
    tools = _tools(runtime)
    listed = _call(tools["inbox_list"], _ENVELOPE, limit=10)
    assert listed.ok and set(listed.data.model_dump()) == {"notifications", "count"}
    assert listed.data.count == 1
    got = _call(tools["inbox_get"], _ENVELOPE, notification_id="n-1")
    assert got.ok and set(got.data.model_dump()) == {"notification"}
    assert got.data.notification.notification_id == "n-1"


def test_mark_read_and_stale_cas(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("n-1", "dk-1"))
    tool = _tools(runtime)["inbox_mark_read"]
    first = _call(tool, _ENVELOPE, notification_id="n-1", expected_revision=1)
    assert first.ok and first.data.notification.revision == 2
    stale = _call(tool, _ENVELOPE, notification_id="n-1", expected_revision=1)
    assert stale.ok is False and stale.error == "notification_revision_conflict"


def test_mark_all_count_fence_no_partial(tmp_path) -> None:
    runtime = _runtime(tmp_path)
    for i in range(3):
        runtime.inbox_store.create_or_replay(_rec(f"n-{i}", f"dk-{i}"))
    tool = _tools(runtime)["inbox_mark_all_read"]
    conflict = _call(tool, _ENVELOPE, expected_unread_count=2)
    assert conflict.ok is False and conflict.error == "notification_unread_count_conflict"
    assert len(runtime.inbox_list(_T, _OWNER, limit=10, unread_only=True)) == 3
    done = _call(tool, _ENVELOPE, expected_unread_count=3)
    assert done.ok and set(done.data.model_dump()) == {"marked_count"}
    assert done.data.marked_count == 3
    assert runtime.inbox_list(_T, _OWNER, limit=10, unread_only=True) == []
