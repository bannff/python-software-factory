"""Authoring path, output-redaction, and bounded-YAML regressions."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any

import pytest
import yaml

from factory.permissions.authoring import AuthoringError, AuthoringManager
from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.server import create_mcp_server


def _call(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name, arguments))


def _server(root: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    monkeypatch.setenv("PERMISSIONS_ENABLE_AUTHORING_TOOLS", "1")
    (root / "policies").mkdir(parents=True, exist_ok=True)
    return create_mcp_server(PermissionsRuntime(root))


def test_public_authoring_paths_are_logical_and_errors_are_sanitized(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    server = _server(tmp_path, monkeypatch)
    status = _call(server, "permissions.authoring.get_status", {})
    assert status.structured_content["data"]["config_dir"] == "."
    assert status.structured_content["data"]["allowed_paths"] == ["policies"]
    assert str(tmp_path) not in str(status.structured_content)

    dry_run = _call(server, "permissions.authoring.upsert_policy", {
        "id": "safe-policy", "yaml_or_object": {"name": "P", "rules": []}, "dry_run": True,
    })
    assert dry_run.structured_content["data"]["path"] == "policies/safe-policy.yaml"
    missing = _call(server, "permissions.authoring.delete_policy", {"id": "missing"})
    assert missing.structured_content["data"]["path"] == "policies/missing.yaml"

    (tmp_path / "policies" / "bad.yaml").write_text(yaml.safe_dump({
        "id": "bad", "name": ["SECRET_TOKEN"], "rules": []
    }))
    validated = _call(server, "permissions.authoring.validate_policies", {})
    payload = validated.structured_content
    assert payload["ok"] is True and payload["data"]["ok"] is False
    assert payload["data"]["errors"][0]["path"] == "policies/bad.yaml"
    assert "SECRET_TOKEN" not in str(payload)
    assert str(tmp_path) not in str(payload)


def test_validate_rejects_symlinked_policy_directory_and_file(tmp_path: Path) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "escape.yaml").write_text("not: a policy")

    config = tmp_path / "config"
    config.mkdir()
    (config / "policies").symlink_to(outside, target_is_directory=True)
    manager = AuthoringManager(config)
    result = manager.validate_all_policies()
    assert result["ok"] is False
    assert result["errors"][0]["path"] == "policies"
    assert str(outside) not in str(result)

    safe_config = tmp_path / "safe-config"
    (safe_config / "policies").mkdir(parents=True)
    (safe_config / "policies" / "escape.yaml").symlink_to(outside / "escape.yaml")
    file_result = AuthoringManager(safe_config).validate_all_policies()
    assert file_result["ok"] is False
    assert file_result["errors"][0]["error"] == "unsafe_policy_path"
    assert str(outside) not in str(file_result)


def test_bounded_yaml_rejects_documents_aliases_and_oversized_files(tmp_path: Path) -> None:
    manager = AuthoringManager(tmp_path)
    for payload, code in [
        ("---\nname: p\n---\nname: q\n", "yaml_document_count"),
        ("name: &name p\nvalue: *name\n", "yaml_alias_not_allowed"),
        ("x" * 65_537, "policy_size_exceeded"),
    ]:
        with pytest.raises(AuthoringError) as raised:
            manager.upsert_policy_definition(id="p", yaml_or_object=payload)
        assert raised.value.code == code

    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "large.yaml").write_bytes(b"x" * 65_537)
    result = manager.validate_all_policies()
    assert result["errors"][0]["error"] == "policy_size_exceeded"
    assert str(tmp_path) not in str(result)


def test_upsert_and_delete_reject_symlink_targets(tmp_path: Path) -> None:
    outside = tmp_path / "outside.yaml"
    outside.write_text("name: outside")
    (tmp_path / "policies").mkdir()
    (tmp_path / "policies" / "p.yaml").symlink_to(outside)
    manager = AuthoringManager(tmp_path)
    for operation in (
        lambda: manager.upsert_policy_definition(id="p", yaml_or_object={"name": "P", "rules": []}),
        lambda: manager.delete_policy_definition(id="p"),
    ):
        with pytest.raises(AuthoringError) as raised:
            operation()
        assert raised.value.code == "unsafe_policy_path"
