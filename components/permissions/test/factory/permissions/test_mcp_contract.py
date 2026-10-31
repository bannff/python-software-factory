"""Acceptance coverage for the complete strict Permissions MCP surface."""
from typing import get_type_hints

import asyncio
import math
from inspect import signature
from pathlib import Path

import pytest
import yaml

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.permissions.runtime.audit import InMemoryAuditStore
from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.server import create_mcp_server

DEFAULT = {
    "deterministic": {
        "permissions.get_capabilities",
        "permissions.health_check",
        "permissions.describe_config_schema",
        "permissions.get_role_registry",
        "permissions.get_policy_registry",
    },
    "operational": {
        "permissions.evaluate",
        "permissions.batch_evaluate",
        "permissions.explain",
    },
}
AUTHORING = {
    "permissions.authoring.get_status",
    "permissions.authoring.validate_policies",
    "permissions.authoring.upsert_policy",
    "permissions.authoring.delete_policy",
}

def _write_config(root: Path) -> None:
    (root / "policies").mkdir(parents=True, exist_ok=True)
    (root / "policies" / "read.yaml").write_text(yaml.safe_dump({
        "id": "read-policy",
        "name": "Read policy",
        "rules": [{
            "id": "allow-read",
            "effect": "allow",
            "actions": ["read"],
            "resource_types": ["document"],
        }],
    }))

def _tools(mcp):
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}

def _tool(mcp, name: str):
    return asyncio.run(mcp.get_tool(name))

def test_exact_default_catalog_and_native_protocols(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", raising=False)
    _write_config(tmp_path)
    mcp = create_mcp_server(PermissionsRuntime(tmp_path))
    tools = _tools(mcp)

    assert set(tools) == DEFAULT["deterministic"] | DEFAULT["operational"]
    assert {
        name for name, tool in tools.items()
        if tool.fn._mcp_category == "deterministic"
    } == DEFAULT["deterministic"]
    assert {
        name for name, tool in tools.items()
        if tool.fn._mcp_category == "operational"
    } == DEFAULT["operational"]
    assert {str(item.uri) for item in asyncio.run(mcp.list_resources())} == {
        "permissions://schemas/policy",
        "permissions://schemas/settings",
        "permissions://schemas/resource",
        "permissions://docs",
        "permissions://templates",
        "permissions://policies",
        "permissions://roles",
        "permissions://factory",
    }
    assert {item.uri_template for item in asyncio.run(mcp.list_resource_templates())} == {
        "permissions://docs/{doc_name}",
        "permissions://templates/{template_name}",
    }
    assert {item.name for item in asyncio.run(mcp.list_prompts())} == {
        "create_policy", "debug_denial", "setup_rbac", "audit_review",
    }

def test_every_live_tool_has_same_brick_strict_typed_boundary(tmp_path: Path) -> None:
    _write_config(tmp_path)
    tools = _tools(create_mcp_server(PermissionsRuntime(tmp_path)))
    assert len(tools) == 8
    for name, tool in tools.items():
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert input_model.__module__.startswith("factory.permissions.mcp.contracts"), name
        assert output_model.__module__.startswith("factory.permissions.mcp.contracts"), name
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert output_model.model_config.get("extra") == "forbid"
        assert output_model.model_config.get("strict") is True
        assert get_type_hints(tool.fn)["return"] == ToolResult[output_model]
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"
        assert output_model.model_json_schema()["type"] == "object"

def test_runtime_capabilities_reconcile_live_default_catalog(tmp_path: Path) -> None:
    _write_config(tmp_path)
    runtime = PermissionsRuntime(tmp_path)
    capabilities = runtime.get_capabilities()
    assert set(capabilities["tools"]["deterministic"]) == DEFAULT["deterministic"]
    assert set(capabilities["tools"]["operational"]) == DEFAULT["operational"]
    assert "permissions.evaluate_cedar" not in str(capabilities)

    result = _tool(create_mcp_server(runtime), "permissions.get_capabilities").fn()
    assert result.ok and result.data is not None
    assert result.data.tools.authoring == []
    assert set(result.data.tools.deterministic) == DEFAULT["deterministic"]

def test_allow_deny_explain_batch_and_audit_order(tmp_path: Path) -> None:
    _write_config(tmp_path)
    runtime = PermissionsRuntime(tmp_path)
    audit = InMemoryAuditStore()
    runtime.set_audit_store(audit)
    mcp = create_mcp_server(runtime)

    allow = _tool(mcp, "permissions.evaluate").fn(
        action="read", resource={"type": "document", "id": "doc-1"},
    )
    deny = _tool(mcp, "permissions.evaluate").fn(
        action="write", resource={"type": "document", "id": "doc-1"},
    )
    assert allow.ok and allow.data.decision == "allow"
    assert deny.ok and deny.data.decision == "deny"

    batch = _tool(mcp, "permissions.batch_evaluate").fn(requests=[
        {"action": "read", "resource": {"type": "document", "id": "1"}},
        {"action": "write", "resource": {"type": "document", "id": "2"}},
    ])
    assert batch.ok and [item.decision for item in batch.data.decisions] == ["allow", "deny"]
    explanation = _tool(mcp, "permissions.explain").fn(
        action="read", resource={"type": "document", "id": "doc-1"},
    )
    assert explanation.ok and explanation.data.matched_rules
    assert [item.action for item in audit.list(limit=10)] == ["write", "read", "write", "read"]


@pytest.mark.parametrize("name,kwargs", [
    ("permissions.get_capabilities", {"extra": True}),
    ("permissions.health_check", {"extra": True}),
    ("permissions.describe_config_schema", {"extra": True}),
    ("permissions.get_role_registry", {"extra": True}),
    ("permissions.get_policy_registry", {"extra": True}),
    ("permissions.evaluate", {"action": "read", "resource": {"type": "doc"}, "extra": True}),
    ("permissions.batch_evaluate", {"requests": [], "extra": True}),
    ("permissions.explain", {"action": "read", "resource": {"type": "doc"}, "extra": True}),
])
def test_every_default_tool_rejects_unknown_fields(tmp_path: Path, name: str, kwargs: dict) -> None:
    tool = _tool(create_mcp_server(PermissionsRuntime(tmp_path)), name)
    with pytest.raises(SchemaMigrationError):
        tool.fn(**kwargs)

def test_nested_coercion_finite_json_and_batch_bounds_are_rejected(tmp_path: Path) -> None:
    tool = _tool(create_mcp_server(PermissionsRuntime(tmp_path)), "permissions.evaluate")
    with pytest.raises(SchemaMigrationError):
        tool.fn(action="read", resource={"type": "document", "unexpected": True})
    with pytest.raises(SchemaMigrationError):
        tool.fn(action=1, resource={"type": "document"})
    with pytest.raises(SchemaMigrationError):
        tool.fn(action="read", resource={"type": "document"}, context={"x": math.nan})
    with pytest.raises(SchemaMigrationError):
        tool.fn(action="read", resource={"type": "document"}, envelope={"attributes": {"x": "a" * 513}})

    batch = _tool(create_mcp_server(PermissionsRuntime(tmp_path)), "permissions.batch_evaluate")
    requests = [{"action": "read", "resource": {"type": "document"}}] * 101
    with pytest.raises(SchemaMigrationError):
        batch.fn(requests=requests)

def test_unexpected_exception_is_safe_and_redacted(tmp_path: Path) -> None:
    class BrokenRuntime:
        _config_dir = tmp_path
        _settings = None

        def get_policies(self):
            raise RuntimeError("/private/path and secret-token")

        def get_role_registry(self):
            return []

    result = _tool(create_mcp_server(BrokenRuntime()), "permissions.health_check").fn()
    assert not result.ok
    assert result.error == "tool_execution_failed"
    assert "/private/path" not in str(result)
    assert "secret-token" not in str(result)
