"""Neutral-catalog contract coverage for Domain's typed public surface."""
from __future__ import annotations

import asyncio
import inspect
import json
from typing import Any

import pytest

from factory.domain.interface import create_server
from factory.domain.registry import unified
from factory.mcp_utils.interface import SchemaMigrationError, ToolResult


DETERMINISTIC = {"domain_get_manifest", "domain_list_manifests"}
OPERATIONAL = {
    "domain_open_engagement", "domain_get_active_engagement", "domain_close_engagement",
}
AUTHORING = {"domain_create_manifest", "domain_delete_manifest"}


@pytest.fixture(autouse=True)
def _reset_store():
    unified.reset_default_store()
    yield
    unified.reset_default_store()


def _server():
    return create_server()


def _tool(server: Any, name: str) -> Any:
    return asyncio.run(server.get_tool(name))


def _wire(tool: Any, arguments: dict[str, Any]) -> dict[str, Any]:
    return tool.fn(**arguments).model_dump(mode="json")


def test_exact_catalog_categories_and_same_brick_dtos() -> None:
    tools = {tool.name: tool for tool in asyncio.run(_server().list_tools())}
    assert set(tools) == DETERMINISTIC | OPERATIONAL | AUTHORING
    for category, names in {
        "deterministic": DETERMINISTIC, "operational": OPERATIONAL, "authoring": AUTHORING,
    }.items():
        assert {name for name, tool in tools.items() if tool.fn._mcp_category == category} == names
    for tool in tools.values():
        input_model, output_model = tool.fn._mcp_input_model, tool.fn._mcp_output_model
        assert input_model.__module__ == output_model.__module__ == "factory.domain.mcp.contracts"
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert str(inspect.signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_raw_strict_inputs_and_total_generic_manifest() -> None:
    server = _server()
    get_manifest = _tool(server, "domain_get_manifest")
    assert list(inspect.signature(get_manifest.fn).parameters) == ["domain_id"]
    with pytest.raises(SchemaMigrationError):
        get_manifest.fn(domain_id=1)
    with pytest.raises(SchemaMigrationError):
        get_manifest.fn(domain_id="x", extra=True)
    with pytest.raises(SchemaMigrationError):
        _tool(server, "domain_list_manifests").fn(extra=True)
    result = _wire(get_manifest, {"domain_id": "arbitrary-input"})
    assert result["ok"] and result["data"]["manifest"]["domain_id"] == "generic"


def test_create_manifest_has_strict_concrete_nested_ingress() -> None:
    create_manifest = _tool(_server(), "domain_create_manifest")
    schema = create_manifest.fn._mcp_input_model.model_json_schema(mode="validation")
    manifest_ref = schema["properties"]["manifest"]["$ref"].rsplit("/", 1)[-1]
    manifest = schema["$defs"][manifest_ref]
    assert manifest["additionalProperties"] is False
    assert set(manifest["properties"]) == {
        "domain_id", "display_name", "labels", "taxonomy_ref", "type_descriptors",
        "severity_palette", "artifact_renderers", "theme", "default_persona_id", "version",
    }
    for name in ("TypeDescriptorInput", "ThemeInput"):
        assert schema["$defs"][name]["additionalProperties"] is False

    for manifest in (
        {"domain_id": "custom", "type_descriptors": {"issue": {"label": "x", "extra": True}}},
        {"domain_id": "custom", "labels": []},
        {"domain_id": "custom", "type_descriptors": {"issue": {"label": 1}}},
    ):
        with pytest.raises(SchemaMigrationError):
            create_manifest.fn(manifest=manifest)


def test_list_lifecycle_persona_and_authoring_negative_data() -> None:
    server = _server()
    listed = _wire(_tool(server, "domain_list_manifests"), {})
    assert listed["ok"] and listed["data"]["count"] == len(listed["data"]["manifests"])

    created = _wire(_tool(server, "domain_create_manifest"), {
        "manifest": {"domain_id": "custom", "default_persona_id": "persona-1"},
    })
    assert created["ok"] and created["data"] == {
        "ok": True, "domain_id": "custom", "deleted": None, "error": None,
    }
    opened = _wire(_tool(server, "domain_open_engagement"), {"domain_id": "custom"})
    assert opened["ok"] and opened["data"]["persona_id"] == "persona-1"
    active = _wire(_tool(server, "domain_get_active_engagement"), {})
    assert active["ok"] and active["data"]["active"]
    assert active["data"]["engagement"]["domain_id"] == "custom"
    closed = _wire(_tool(server, "domain_close_engagement"), {})
    assert closed["ok"] and closed["data"] == {"ok": True, "active": False}

    invalid = _wire(_tool(server, "domain_create_manifest"), {"manifest": {"domain_id": "INVALID"}})
    assert invalid["ok"] and invalid["data"]["ok"] is False and invalid["data"]["error"]
    missing = _wire(_tool(server, "domain_delete_manifest"), {"domain_id": "missing"})
    assert missing["ok"] and missing["data"]["ok"] is False and "not found" in missing["data"]["error"]
    deleted = _wire(_tool(server, "domain_delete_manifest"), {"domain_id": "custom"})
    assert deleted["ok"] and deleted["data"]["deleted"] is True


def test_resources_and_prompts_remain_native_protocol_surfaces() -> None:
    server = _server()
    templates = {str(item.uri_template) for item in asyncio.run(server.list_resource_templates())}
    assert templates == {"domain://manifests/{domain_id}"}
    resource = asyncio.run(server.read_resource("domain://manifests/arbitrary")).contents[0].content
    assert json.loads(resource)["domain_id"] == "generic"
    prompt = asyncio.run(server.render_prompt("open_domain_engagement", {"domain_id": "wine"}))
    assert "'wine'" in prompt.messages[0].content.text


def test_handlers_return_tool_results() -> None:
    result = _tool(_server(), "domain_get_manifest").fn(domain_id="x")
    assert isinstance(result, ToolResult) and result.ok and result.data.manifest.domain_id == "generic"
