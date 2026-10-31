"""Service-only authorization for the trusted ``inbox_publish`` projection.

Drives the real native dispatch rail (MCPAggregator + NativeEnvelopeInvoker) to
prove the tool is callable only by caller ``scheduler`` under an exact six-field
``projection`` binding: a public/foreign caller is denied, a binding that does
not match the arguments is denied, an ambient owner mismatch and a content
digest mismatch are fixed safe failures, and a valid scheduler call persists the
durable record. Not a public create tool.
"""
from __future__ import annotations

import asyncio

import pytest

from factory.mcp_server.runtime.aggregator import MCPAggregator
from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker
from factory.mcp_utils.interface import ServiceOnlyAccessError
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.inbox_projection import material_digest
from factory.notification.server import create_mcp_server

_T, _OWNER, _SID = "tenant", "owner", "nightly"
_DK = "scheduler-auto-pause:nightly:5"
_TITLE = "Schedule auto-paused"
_BODY = "Schedule nightly was auto-paused after five consecutive failed runs."
_TARGET = {"brick_name": "notification", "tool_name": "inbox_publish"}


def _digest(**over) -> str:
    base = dict(event_type="scheduler.schedule.auto_paused", subject_id=_SID,
                revision=5, dedupe_key=_DK, priority="critical", title=_TITLE,
                body=_BODY)
    base.update(over)
    return material_digest(**base)


def _binding(**over) -> dict:
    base = dict(tenant_id=_T, owner_id=_OWNER,
                event_type="scheduler.schedule.auto_paused", subject_id=_SID,
                revision=5, payload_digest=_digest())
    base.update(over)
    return base


def _arguments(binding: dict, **over) -> dict:
    base = {**binding, "dedupe_key": _DK, "priority": "critical",
            "title": _TITLE, "body": _BODY}
    base.update(over)
    return base


def _fixture(tmp_path):
    runtime = NotificationRuntime(tmp_path)
    catalog = create_mcp_server(runtime)
    aggregator = MCPAggregator(ToolCatalog("root"))
    aggregator.set_available_bricks(["notification"])
    aggregator._lazy._cache["notification"] = catalog
    return runtime, catalog, aggregator


def _call(aggregator, caller: str, *, arguments: dict, binding: dict,
          envelope: dict, key: str):
    return NativeEnvelopeInvoker(aggregator).for_caller(caller)(
        _TARGET, arguments=arguments, projection=binding,
        idempotency_key=key, envelope=envelope)


def test_scheduler_caller_persists_and_returns_typed_success(tmp_path) -> None:
    runtime, _catalog, aggregator = _fixture(tmp_path)
    binding = _binding()
    result = _call(aggregator, "scheduler", arguments=_arguments(binding),
                   binding=binding, envelope={"principal_id": _OWNER, "tenant_id": _T},
                   key="ok-1")
    structured = result["result"]["structured_content"]
    assert structured["ok"] is True
    data = structured["data"]
    assert data["persisted"] is True and data["status"] == "created"
    stored = runtime.inbox_get(_T, _OWNER, data["notification_id"])
    assert stored.dedupe_key == _DK


def test_direct_call_without_native_dispatch_is_denied(tmp_path) -> None:
    _runtime, catalog, _aggregator = _fixture(tmp_path)
    direct = asyncio.run(catalog.get_tool("inbox_publish"))
    with pytest.raises(ServiceOnlyAccessError):
        asyncio.run(direct.fn(**_arguments(_binding())))


def test_public_dispatch_is_denied(tmp_path) -> None:
    _runtime, _catalog, aggregator = _fixture(tmp_path)
    public = asyncio.run(aggregator.call_public_brick_tool(
        "notification", "inbox_publish", _arguments(_binding())))
    assert public["ok"] is False


def test_foreign_caller_is_denied(tmp_path) -> None:
    _runtime, _catalog, aggregator = _fixture(tmp_path)
    binding = _binding()
    result = _call(aggregator, "agent", arguments=_arguments(binding),
                   binding=binding, envelope={"principal_id": _OWNER, "tenant_id": _T},
                   key="foreign-1")
    assert result["error"]["type"] == "ServiceOnlyAccessError"


def test_binding_not_matching_arguments_is_denied(tmp_path) -> None:
    _runtime, _catalog, aggregator = _fixture(tmp_path)
    binding = _binding()
    # Arguments claim a different schedule than the bound subject_id.
    tampered = _arguments(binding, subject_id="other")
    result = _call(aggregator, "scheduler", arguments=tampered, binding=binding,
                   envelope={"principal_id": _OWNER, "tenant_id": _T}, key="mismatch-1")
    assert result["error"]["type"] == "ServiceOnlyAccessError"


def test_ambient_owner_mismatch_is_fixed_safe_failure(tmp_path) -> None:
    runtime, _catalog, aggregator = _fixture(tmp_path)
    binding = _binding()
    result = _call(aggregator, "scheduler", arguments=_arguments(binding),
                   binding=binding, envelope={"principal_id": "intruder", "tenant_id": _T},
                   key="ambient-1")
    structured = result["result"]["structured_content"]
    assert structured["ok"] is False
    assert structured["error"] == "notification_projection_authority_mismatch"
    assert runtime.inbox_list(_T, _OWNER, limit=10) == []


def test_content_digest_mismatch_is_fixed_safe_failure(tmp_path) -> None:
    runtime, _catalog, aggregator = _fixture(tmp_path)
    # A syntactically valid digest that does not match the bound content.
    binding = _binding(payload_digest="a" * 64)
    result = _call(aggregator, "scheduler", arguments=_arguments(binding),
                   binding=binding, envelope={"principal_id": _OWNER, "tenant_id": _T},
                   key="digest-1")
    structured = result["result"]["structured_content"]
    assert structured["ok"] is False
    assert structured["error"] == "notification_projection_digest_mismatch"
    assert runtime.inbox_list(_T, _OWNER, limit=10) == []
