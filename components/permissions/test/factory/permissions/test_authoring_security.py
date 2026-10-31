"""Authoring registration gates and typed authoring boundary behavior."""
from __future__ import annotations

import asyncio
from inspect import signature
from typing import get_type_hints
import os
from pathlib import Path

import pytest
import yaml

from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.permissions.authoring import AuthoringError, AuthoringManager, authoring_enabled
from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.server import create_mcp_server

AUTHORING = {
    "permissions.authoring.get_status",
    "permissions.authoring.validate_policies",
    "permissions.authoring.upsert_policy",
    "permissions.authoring.delete_policy",
}
BASE = {
    "permissions.get_capabilities",
    "permissions.health_check",
    "permissions.describe_config_schema",
    "permissions.get_role_registry",
    "permissions.get_policy_registry",
    "permissions.evaluate",
    "permissions.batch_evaluate",
    "permissions.explain",
}


def _runtime_root(root: Path, enabled: bool | None = None) -> PermissionsRuntime:
    (root / "policies").mkdir(parents=True, exist_ok=True)
    if enabled is not None:
        (root / "settings.yaml").write_text(yaml.safe_dump({
            "authoring": {"enabled": enabled},
            "policy_store": {"policies_subdir": "policies"},
        }))
    return PermissionsRuntime(root)


def _tool_names(runtime: PermissionsRuntime) -> set[str]:
    mcp = create_mcp_server(runtime)
    return {tool.name for tool in asyncio.run(mcp.list_tools())}


def test_authoring_disabled_by_default() -> None:
    os.environ.pop("PERMISSIONS_ENABLE_AUTHORING_TOOLS", None)
    assert authoring_enabled({"authoring": {"enabled": False}}) is False


def test_authoring_config_cannot_enable_without_env_var() -> None:
    os.environ.pop("PERMISSIONS_ENABLE_AUTHORING_TOOLS", None)
    assert authoring_enabled({"authoring": {"enabled": True}}) is False


def test_authoring_env_var_enables() -> None:
    os.environ["PERMISSIONS_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        assert authoring_enabled({}) is True
        assert authoring_enabled({"authoring": {"enabled": True}}) is True
        assert authoring_enabled({"authoring": {"enabled": False}}) is False
    finally:
        os.environ.pop("PERMISSIONS_ENABLE_AUTHORING_TOOLS", None)


def test_real_factory_authoring_gates_preserve_omitted_config(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.delenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", raising=False)
    assert not AUTHORING.intersection(_tool_names(_runtime_root(tmp_path / "no-env", True)))

    monkeypatch.setenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", "1")
    assert not AUTHORING.intersection(_tool_names(_runtime_root(tmp_path / "explicit-false", False)))
    assert _tool_names(_runtime_root(tmp_path / "omitted")) == BASE | AUTHORING
    assert _tool_names(_runtime_root(tmp_path / "explicit-true", True)) == BASE | AUTHORING
    # This proves registration semantics only; principal authorization is outside this edge.


def test_enabled_authoring_has_strict_same_brick_contracts(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", "1")
    mcp = create_mcp_server(_runtime_root(tmp_path))
    tools = {tool.name: tool for tool in asyncio.run(mcp.list_tools())}
    caps = tools["permissions.get_capabilities"].fn()
    assert caps.ok and set(caps.data.tools.authoring) == AUTHORING
    for name in AUTHORING:
        tool = tools[name]
        input_model = tool.fn._mcp_input_model
        output_model = tool.fn._mcp_output_model
        assert tool.fn._mcp_category == "authoring"
        assert input_model.__module__.startswith("factory.permissions.mcp.contracts")
        assert output_model.__module__.startswith("factory.permissions.mcp.contracts")
        assert input_model.model_config.get("extra") == "forbid"
        assert input_model.model_config.get("strict") is True
        assert get_type_hints(tool.fn)["return"] == ToolResult[output_model]
        assert str(signature(tool.fn).return_annotation) == f"ToolResult[{output_model.__name__}]"


def test_enabled_authoring_real_runtime_returns_typed_domain_outcomes(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", "1")
    mcp = create_mcp_server(_runtime_root(tmp_path))

    status = asyncio.run(mcp.get_tool("permissions.authoring.get_status")).fn()
    assert status.ok and status.data.enabled is True

    invalid = asyncio.run(mcp.get_tool("permissions.authoring.upsert_policy")).fn(
        id="invalid-policy",
        yaml_or_object={"name": "bad", "rules": [{"id": "r", "effect": "invalid"}]},
    )
    assert invalid.ok and invalid.data.ok is False
    assert invalid.data.error == "validation_error"

    dry_run = asyncio.run(mcp.get_tool("permissions.authoring.upsert_policy")).fn(
        id="policy-1", yaml_or_object={"name": "P", "rules": []}, dry_run=True,
    )
    assert dry_run.ok and dry_run.data.ok and dry_run.data.dry_run is True

    missing = asyncio.run(mcp.get_tool("permissions.authoring.delete_policy")).fn(id="missing")
    assert missing.ok and missing.data.deleted is False
    (tmp_path / "policies" / "bad.yaml").write_text(yaml.safe_dump({
        "id": "bad", "name": "bad",
        "rules": [{"id": "r", "effect": "invalid"}],
    }))
    validated = asyncio.run(mcp.get_tool("permissions.authoring.validate_policies")).fn()
    assert validated.ok and validated.data.ok is False and validated.data.errors

    with pytest.raises(SchemaMigrationError):
        asyncio.run(mcp.get_tool("permissions.authoring.upsert_policy")).fn(
            id="policy-1", yaml_or_object={}, dry_run="false",
        )


def test_traversal_protection(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    outside = tmp_path / "outside"
    outside.mkdir()
    (cfg / "policies").symlink_to(outside, target_is_directory=True)

    mgr = AuthoringManager(cfg)
    with pytest.raises(AuthoringError):
        _ = mgr._policy_path("escape")
