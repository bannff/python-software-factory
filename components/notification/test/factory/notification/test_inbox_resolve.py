"""Unit tests for the owner-scoped deep-link target resolver.

Covers strict ingress (no tenant/owner input), all seven exact source mappings,
positive source authorization, the single fixed opaque failure byte-shape for
every deviation, source-payload suppression, the "no service binding kwarg"
contract, ambient-envelope propagation, the canonical url/path rejection at the
target union, and a runtime no-import guard.
"""
from __future__ import annotations

import ast
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from pydantic import ValidationError

from factory.mcp_utils.interface import (
    ToolCatalog, reset_envelope, set_envelope, set_service,
)
from factory.notification.mcp import inbox_resolve
from factory.notification.mcp.contracts.inbox_resolve import InboxResolveInput
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_models import NotificationRecord, Priority
from factory.notification.runtime.inbox_resolve import (
    TargetNotResolved, authorize_target,
)
from factory.notification.runtime.inbox_targets import SessionTarget, build_target

_T, _OWNER = "tenant-1", "owner-1"
_NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)
_ENV = {"tenant_id": _T, "principal_id": _OWNER}
_FIXED = "notification_target_not_found"
_MAP = {
    "session": ("session", "session_get", "session_id", False),
    "workflow_run": ("workflow", "workflow.get_run", "run_id", True),
    "schedule": ("scheduler", "scheduler_get", "schedule_id", False),
    "artifact": ("artifacts", "artifacts_get", "slug", False),
    "crew": ("agent", "agent_get_crew", "crew_id", False),
    "lesson": ("lessons", "lessons_get", "lesson_id", False),
    "canvas": ("ui", "ui_resolve_canvas", "view_id", False),
}


def _success(data: dict | None = None) -> dict:
    return {"ok": True, "result": {"kind": "tool", "structured_content": {
        "schema_version": "v1", "ok": True, "data": data or {"x": 1},
        "error": None}}}


class _Recorder:
    def __init__(self, transport: object | None = None) -> None:
        self.transport = _success() if transport is None else transport
        self.calls: list[dict] = []
        self.caller: str | None = None

    def factory(self, caller: str):
        self.caller = caller

        def bound(target, *, arguments, idempotency_key, envelope, **binding):
            self.calls.append({
                "target": target, "arguments": arguments, "binding": binding,
                "idempotency_key": idempotency_key, "envelope": envelope})
            return self.transport

        return bound


def _rec(nid: str, target, owner: str = _OWNER) -> NotificationRecord:
    return NotificationRecord(
        tenant_id=_T, owner_id=owner, notification_id=nid, kind="k",
        title="hello", priority=Priority.DEFAULT, target=target,
        dedupe_key=nid, created_at=_NOW)


def _tool(runtime: NotificationRuntime):
    catalog = ToolCatalog("test")
    inbox_resolve.register(catalog, runtime)
    return {t.name: t for t in asyncio.run(catalog.list_tools())}["inbox_resolve_target"]


def _call(tool, envelope, **kwargs):
    token = set_envelope(envelope) if envelope is not None else None
    try:
        return tool.fn(**kwargs)
    finally:
        reset_envelope(token)


def _bytes(result) -> str:
    return json.dumps(result.model_dump(), sort_keys=True)


def test_ingress_rejects_identity_and_bad_id() -> None:
    with pytest.raises(ValidationError):
        InboxResolveInput(notification_id="n-1", tenant_id=_T)
    with pytest.raises(ValidationError):
        InboxResolveInput(notification_id="bad id")
    assert InboxResolveInput(notification_id="n-1").notification_id == "n-1"


@pytest.mark.parametrize("kind,expected", _MAP.items())
def test_each_mapping_is_exact_and_authorizes(tmp_path, kind, expected) -> None:
    brick, tool_name, arg, pass_env = expected
    ident = "welcome" if kind == "canvas" else f"{kind}-id"
    runtime = NotificationRuntime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("n-1", build_target(kind, ident)))
    rec = _Recorder()
    set_service("tool_invoker_for_caller", rec.factory)
    result = _call(_tool(runtime), _ENV, notification_id="n-1")
    call = rec.calls[-1]
    assert result.ok is True and rec.caller == "notification"
    assert call["target"] == {"brick_name": brick, "tool_name": tool_name}
    assert call["arguments"][arg] == ident
    assert ("envelope" in call["arguments"]) is pass_env
    assert call["binding"] == {} and call["idempotency_key"] == "n-1"
    assert call["envelope"]["tenant_id"] == _T
    assert call["envelope"]["principal_id"] == _OWNER


def test_success_returns_only_typed_target_no_payload(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("n-1", SessionTarget(session_id="s9")))
    set_service("tool_invoker_for_caller",
                _Recorder(_success({"title": "SECRET"})).factory)
    dumped = _call(_tool(runtime), _ENV, notification_id="n-1").data.model_dump()
    assert set(dumped) == {"authorized", "target"} and dumped["authorized"] is True
    assert dumped["target"] == {"kind": "session", "session_id": "s9"}
    assert "SECRET" not in json.dumps(dumped)


def test_all_deviations_collapse_to_one_fixed_shape(tmp_path) -> None:
    runtime = NotificationRuntime(tmp_path)
    runtime.inbox_store.create_or_replay(_rec("mine", SessionTarget(session_id="s")))
    runtime.inbox_store.create_or_replay(
        _rec("foreign", SessionTarget(session_id="s"), owner="owner-2"))

    def run(nid, env, transport):
        set_service("tool_invoker_for_caller", _Recorder(transport).factory)
        return _call(_tool(runtime), env, notification_id=nid)

    deleted = _success(); deleted["result"]["structured_content"].update(ok=False, data=None)
    no_data = _success(); no_data["result"]["structured_content"]["data"] = None
    results = [
        run("missing", _ENV, _success()),                             # absent record
        run("foreign", _ENV, _success()),                             # foreign record
        run("mine", _ENV, deleted),                                   # deleted source
        run("mine", _ENV, {"ok": False, "error": {"type": "X", "message": "m"}}),
        run("mine", _ENV, {"ok": True, "result": {"kind": "task", "structured_content": {}}}),
        run("mine", _ENV, "nope"),                                    # non-dict transport
        run("mine", _ENV, no_data),                                   # unexpected payload
        run("mine", None, _success()),                                # absent identity
    ]
    set_service("tool_invoker_for_caller", None)                      # missing invoker
    results.append(_call(_tool(runtime), _ENV, notification_id="mine"))
    expected = _bytes(results[0])
    for result in results:
        assert result.ok is False and result.error == _FIXED
        assert _bytes(result) == expected


def test_unsupported_kind_and_missing_invoker_raise() -> None:
    class _Fake:
        kind = "mystery"

    with pytest.raises(TargetNotResolved):
        authorize_target(_Fake(), invoker_factory=lambda c: (lambda *a, **k: _success()),
                         envelope=_ENV, idempotency_key="k")
    with pytest.raises(TargetNotResolved):
        authorize_target(SessionTarget(session_id="s"), invoker_factory=None,
                         envelope=_ENV, idempotency_key="k")


@pytest.mark.parametrize("bad", ["http://evil", "a/b", "../escape", "has space"])
def test_target_union_rejects_urls_and_paths(bad) -> None:
    with pytest.raises(ValidationError):
        SessionTarget(session_id=bad)
    with pytest.raises(ValueError):
        build_target("session", bad)


def test_resolver_runtime_imports_no_source_runtimes() -> None:
    tree = ast.parse(Path(
        "components/notification/src/factory/notification/runtime/inbox_resolve.py"
    ).read_text())
    forbidden = {"session", "workflow", "scheduler", "artifacts", "agent", "lessons", "ui"}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            parts = node.module.split(".")
            assert not (parts[0] == "factory" and len(parts) > 1 and parts[1] in forbidden), \
                node.module
