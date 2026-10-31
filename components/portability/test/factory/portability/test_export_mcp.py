"""portability_export_preview / portability_export MCP tools."""
from __future__ import annotations

import asyncio

import pytest
from factory.mcp_utils.interface import get_service, reset_envelope, set_envelope, set_service

from factory.portability.server import create_mcp_server

MEMORY_ROWS = [{"id": "m1", "content": "hello", "memory_type": "semantic", "tags": []}]


def _ok(data: dict) -> dict:
    return {"ok": True, "result": {"structured_content": {"ok": True, "data": data}}}


def _invoker():
    def factory(caller: str):
        def invoke(target, *, arguments, idempotency_key, envelope):
            routes = {
                ("memory", "memory_list"): {"memories": MEMORY_ROWS},
                ("kb", "kb_list_documents"): {"documents": []},
                ("lessons", "lessons_list"): {"lessons": []},
                ("scheduler", "scheduler_list"): {"schedules": []},
                ("ui", "ui_get_display_preferences"): {"theme": "dark"},
            }
            return _ok(routes[(target["brick_name"], target["tool_name"])])
        return invoke
    return factory


@pytest.fixture(autouse=True)
def _envelope():
    previous = get_service("tool_invoker_for_caller")
    set_service("tool_invoker_for_caller", _invoker())
    token = set_envelope({"tenant_id": "tenant-a", "principal_id": "owner-a"})
    yield
    reset_envelope(token)
    set_service("tool_invoker_for_caller", previous)


def _call(catalog, name: str, **kwargs):
    return asyncio.run(catalog.call_tool(name, kwargs))


def test_export_preview_reports_counts_with_no_file_written(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTABILITY_EXPORT_ROOT", str(tmp_path))
    catalog = create_mcp_server()
    result = _call(catalog, "portability_export_preview", kinds=["memory"])
    data = result.structured_content["data"]
    assert data["kinds"][0]["kind"] == "memory"
    assert data["kinds"][0]["count"] == 1
    assert list(tmp_path.iterdir()) == []  # preview never writes


def test_export_writes_a_real_file_and_returns_its_path(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTABILITY_EXPORT_ROOT", str(tmp_path))
    catalog = create_mcp_server()
    result = _call(catalog, "portability_export", destination_name="backup.cxbundle.json", kinds=["memory"])
    data = result.structured_content["data"]
    assert data["path"] == str(tmp_path / "backup.cxbundle.json")
    assert (tmp_path / "backup.cxbundle.json").exists()
    assert data["bytes_written"] > 0


def test_export_rejects_a_traversal_destination_name(tmp_path, monkeypatch):
    monkeypatch.setenv("PORTABILITY_EXPORT_ROOT", str(tmp_path))
    catalog = create_mcp_server()
    result = _call(catalog, "portability_export", destination_name="../escape.json", kinds=["memory"])
    assert result.structured_content["ok"] is False
