from __future__ import annotations

import asyncio

from factory.devtools.runtime.runtime import DevtoolsRuntime
from factory.devtools.server import create_tool_catalog
from factory.mcp_utils.interface import set_service


def _list_dir(**kwargs):
    catalog = create_tool_catalog(DevtoolsRuntime())
    return asyncio.run(asyncio.run(catalog.get_tool("devtools_list_dir")).fn(**kwargs))


def test_missing_thread_is_a_typed_failure_not_tool_execution_failed() -> None:
    result = _list_dir(path=".", envelope={})
    assert not result.ok
    assert result.error == "devtools_session_required"


def test_unresolvable_session_is_a_typed_failure() -> None:
    set_service("tool_invoker_for_caller", lambda _caller: (
        lambda *_a, **_k: {"ok": True, "result": {"structured_content": {
            "ok": False, "error": "session_not_found"}}}
    ))
    try:
        result = _list_dir(path=".", envelope={"thread_id": "t"})
    finally:
        set_service("tool_invoker_for_caller", None)
    assert result.error == "devtools_session_unavailable"


def test_session_without_project_is_a_typed_failure() -> None:
    session = {"tenant_id": "t", "owner_id": "o", "session_id": "s", "project": ""}
    set_service("tool_invoker_for_caller", lambda _caller: (
        lambda *_a, **_k: {"ok": True, "result": {"structured_content": {
            "ok": True, "data": {"session": session}}}}
    ))
    try:
        result = _list_dir(path=".", envelope={"thread_id": "t"})
    finally:
        set_service("tool_invoker_for_caller", None)
    assert result.error == "devtools_project_unbound"
