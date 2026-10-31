"""Fresh-server contract coverage for Notification's strict typed MCP boundary."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path
from typing import Any

import pytest
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.notification.runtime.dispatcher import NotificationRuntime
from factory.notification.runtime.models import DeliveryStatus
from factory.notification.server import create_mcp_server

DETERMINISTIC = {"get_capabilities", "health_check", "get_channel_registry", "get_template_registry", "describe_config_schema", "inbox_list", "inbox_get", "inbox_resolve_target", "get_preferences"}
OPERATIONAL = {"send_notification", "get_delivery_status", "list_deliveries", "inbox_mark_read", "inbox_mark_all_read", "inbox_publish", "update_preferences"}
AUTHORING = {"authoring_status", "upsert_channel_config", "delete_channel_config", "upsert_template_config", "delete_template_config"}


def _server(path: Path, monkeypatch: pytest.MonkeyPatch, enabled: bool = False):
    monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1" if enabled else "0")
    return create_mcp_server(NotificationRuntime(path))


class _Tool:
    def __init__(self, server: Any, name: str) -> None:
        self.server, self.name = server, name
        self.fn = asyncio.run(server.get_tool(name)).fn

    async def run(self, arguments: dict[str, Any]):
        return await self.server.call_tool(self.name, arguments)


def _tool(server: Any, name: str) -> Any:
    return _Tool(server, name)


def _wire(tool: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    return json.loads(asyncio.run(tool.run(arguments)).content[0].text)


def test_catalog_categories_dtos_and_exact_egress(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tools = {tool.name: tool for tool in asyncio.run(_server(tmp_path, monkeypatch).list_tools())}
    assert set(tools) == DETERMINISTIC | OPERATIONAL | AUTHORING
    for category, names in (("deterministic", DETERMINISTIC), ("operational", OPERATIONAL), ("authoring", AUTHORING)):
        assert {name for name, tool in tools.items() if tool.fn._mcp_category == category} == names
    for tool in tools.values():
        input_model, output_model = tool.fn._mcp_input_model, tool.fn._mcp_output_model
        assert input_model.__module__.startswith("factory.notification.mcp.contracts")
        assert output_model.__module__.startswith("factory.notification.mcp.contracts")
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert str(inspect.signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_transport_rejects_raw_types_unknowns_bounds_and_envelope(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    tool = _tool(_server(tmp_path, monkeypatch), "send_notification")
    invalid = [
        {"recipient": 1}, {"recipient": "   "}, {"recipient": "x", "priority": "urgent"},
        {"recipient": "x", "data": []}, {"recipient": "x", "unknown": True},
        {"recipient": "x", "envelope": {"unknown": True}},
    ]
    for arguments in invalid:
        with pytest.raises(SchemaMigrationError, match="validation failed"):
            asyncio.run(tool.run(arguments))
    deliveries = _tool(_server(tmp_path, monkeypatch), "list_deliveries")
    for arguments in ({"limit": "1"}, {"limit": 101}, {"offset": -1}, {"status": "unknown"}):
        with pytest.raises(SchemaMigrationError, match="validation failed"):
            asyncio.run(deliveries.run(arguments))
    assert _wire(tool, {"recipient": "ok", "content": "body", "envelope": {}})["ok"]


def test_defaults_normal_negatives_and_redaction(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = _server(tmp_path, monkeypatch)
    missing = _wire(_tool(server, "get_delivery_status"), {"message_id": "missing"})
    assert missing == {"schema_version": "v1", "ok": True, "data": {
        "message_id": None, "status": None, "backend": None, "recipient": None,
        "channel_id": None, "timestamp": None, "error": "not_found", "found": False,
    }, "error": None, "idempotency_key": None}
    listed = _wire(_tool(server, "list_deliveries"), {})
    assert listed["ok"] and listed["data"] == {"deliveries": [], "count": 0}
    capabilities = _wire(_tool(server, "get_capabilities"), {})
    assert "config_dir" not in json.dumps(capabilities)
    status = _wire(_tool(server, "authoring_status"), {})
    assert status["data"] == {"enabled": False, "env_var": "NOTIFY_ENABLE_AUTHORING_TOOLS"}
    disabled = _wire(_tool(server, "delete_channel_config"), {"channel_id": "missing"})
    assert disabled["ok"] and disabled["data"]["error"] == "authoring_disabled"


def test_send_failed_delivery_is_successful_redacted_domain_result(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    class FailedBackend:
        name = "fake-provider"

        async def send(self, request: Any) -> DeliveryStatus:
            return DeliveryStatus(
                message_id="failed-message",
                status="failed",
                backend=self.name,
                error="provider secret: token=super-secret",
            )

    runtime = NotificationRuntime(tmp_path)
    server = create_mcp_server(runtime)
    runtime.backend = FailedBackend()  # type: ignore[assignment]

    result = _wire(_tool(server, "send_notification"), {"recipient": "user@example.com"})

    assert result["ok"] is True
    assert result["data"]["sent"] is False
    assert result["data"]["status"] == "failed"
    assert result["data"]["error"] == "provider_failed"
    assert "super-secret" not in json.dumps(result)


def test_authoring_success_miss_and_safe_unexpected_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1")
    runtime = NotificationRuntime(tmp_path)
    server = create_mcp_server(runtime)
    channel = _wire(_tool(server, "upsert_channel_config"), {
        "channel_id": "safe-id", "type": "console", "config": {"prefix": "x"},
    })
    assert channel["ok"] and channel["data"] == {"ok": True, "written": True, "identifier": "safe-id", "deleted": None, "error": None}
    missing = _wire(_tool(server, "delete_template_config"), {"template_id": "missing"})
    assert missing["ok"] and missing["data"]["deleted"] is False
    tool = _tool(server, "list_deliveries")
    original = runtime.list_deliveries
    runtime.list_deliveries = lambda *args: (_ for _ in ()).throw(RuntimeError("/secret/path"))  # type: ignore[method-assign]
    try:
        result = tool.fn()
        assert isinstance(result, ToolResult) and not result.ok and result.error == "notification_operation_failed"
    finally:
        runtime.list_deliveries = original  # type: ignore[method-assign]


def test_resources_and_prompts_remain_native(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = _server(tmp_path, monkeypatch)
    resources = {str(item.uri) for item in asyncio.run(server.list_resources())}
    assert "notification://schemas/request" in resources and "notification://deliveries" in resources
    prompts = {item.name for item in asyncio.run(server.list_prompts())}
    assert prompts == {"configure_channel", "debug_delivery", "create_template"}
    prompt = asyncio.run(server.render_prompt("create_template", {"template_id": "x", "name": "X"}))
    assert "x" in prompt.messages[0].content.text
