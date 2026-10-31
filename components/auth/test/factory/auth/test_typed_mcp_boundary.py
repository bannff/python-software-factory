"""Whole-server typed boundary tests for Auth MCP tools."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any, get_type_hints

import pytest
import yaml
from pydantic import ValidationError

from factory.auth.mcp.contracts.models import UpsertBackendConfigInput
from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult

_EXPECTED = {
    "auth.get_capabilities": "deterministic",
    "auth.health_check": "deterministic",
    "auth.describe_config_schema": "deterministic",
    "auth_get_views": "deterministic",
    "auth.verify_access_token": "operational",
    "auth.introspect_token": "operational",
    "auth.resolve_principal": "operational",
    "auth.refresh_token": "operational",
    "auth.revoke_token": "operational",
    "auth.get_user_info": "operational",
    "auth.exchange_token": "operational",
    "auth.authoring.get_status": "authoring",
    "auth.authoring.validate_backend_config": "authoring",
    "auth.authoring.upsert_backend_config": "authoring",
    "auth.authoring.delete_backend_config": "authoring",
    "auth.issue_workload_credential": "operational",
    "auth.revoke_workload_credential": "operational",
    "auth.credentialed_egress": "operational",
    "auth.oauth_enroll_begin": "operational",
    "auth.oauth_enroll_complete": "operational",
}


def _server(tmp_path: Path, *, authoring: bool = False):
    (tmp_path / "backends").mkdir()
    settings: dict[str, Any] = {"service_name": "auth-test", "backend": "memory"}
    if authoring:
        settings["authoring"] = {"enabled": True}
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump(settings))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = AuthRuntime(tmp_path)
    return create_mcp_server(runtime), runtime


def _tool(server, name: str):
    return asyncio.run(server.get_tool(name))


def test_all_17_tools_have_strict_same_brick_boundaries(tmp_path: Path) -> None:
    server, _ = _server(tmp_path)
    assert {tool.name for tool in asyncio.run(server.list_tools())} == set(_EXPECTED)
    for name, category in _EXPECTED.items():
        fn = _tool(server, name).fn
        assert fn._mcp_category == category
        input_model, output_model = fn._mcp_input_model, fn._mcp_output_model
        assert input_model.__module__.startswith("factory.auth.mcp.contracts")
        assert output_model.__module__.startswith("factory.auth.mcp.contracts")
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        assert get_type_hints(fn)["return"] == ToolResult[output_model]


def test_catalog_preserves_dot_names_categories_and_defaults(tmp_path: Path) -> None:
    server, _ = _server(tmp_path)
    schemas = {
        tool.name: tool.fn._mcp_input_model.model_json_schema(mode="validation")
        for tool in asyncio.run(server.list_tools())
    }
    assert schemas["auth.verify_access_token"]["properties"]["required_audience"]["default"] is None
    assert schemas["auth.refresh_token"]["properties"]["scope"]["default"] is None
    assert schemas["auth.authoring.validate_backend_config"]["properties"]["dry_run"]["default"] is True
    assert schemas["auth.authoring.upsert_backend_config"]["properties"]["dry_run"]["default"] is False


def test_unknown_kwargs_are_rejected_at_all_tool_boundaries(tmp_path: Path) -> None:
    server, _ = _server(tmp_path)
    for name in _EXPECTED:
        tool = _tool(server, name)
        kwargs = _minimal_args(name)
        with pytest.raises(Exception):
            tool.fn(**kwargs, unexpected=True)


def test_memory_backend_success_and_expected_domain_negatives(tmp_path: Path) -> None:
    server, runtime = _server(tmp_path)
    backend = runtime._backend
    assert backend is not None
    backend.add_user("u1", "alice", email="a@example.test", scopes=["read"])
    token, refresh = backend.create_token("u1", scopes=["read"], with_refresh=True)
    verified = _tool(server, "auth.verify_access_token").fn(token=token, required_scopes=["read"])
    assert verified.ok and verified.data.ok and verified.data.principal["subject"] == "u1"
    assert token not in verified.model_dump_json()
    inactive = _tool(server, "auth.introspect_token").fn(token="missing")
    assert inactive.ok and inactive.data.active is False and inactive.data.error == "invalid_or_expired"
    missing = _tool(server, "auth.verify_access_token").fn(token="missing")
    assert missing.ok and missing.data.ok is False and missing.data.error == "invalid_token"
    refreshed = _tool(server, "auth.refresh_token").fn(refresh_token=refresh)
    assert refreshed.ok and refreshed.data.issued is True
    assert "access_token" not in refreshed.data.model_dump()


def test_absence_authoring_outcomes_and_views_are_success_data(tmp_path: Path) -> None:
    server, runtime = _server(tmp_path)
    runtime._backend = None
    absent = _tool(server, "auth.get_user_info").fn(access_token="secret-token")
    assert absent.ok and absent.data.ok is False and absent.data.error == "backend_not_configured"
    disabled = _tool(server, "auth.authoring.upsert_backend_config").fn(name="new", yaml_or_object={})
    assert disabled.ok and disabled.data.ok is False and disabled.data.error == "authoring_disabled"
    views = _tool(server, "auth_get_views").fn()
    assert views.ok and views.data.views[0]["id"] == "auth-manager"
    assert "auth_auth.verify_access_token" in str(views.data.views)


def test_upsert_contract_accepts_json_compatible_forms_and_rejects_objects() -> None:
    string_value = "kind: keycloak\nrealm: example"
    object_value = {"kind": "keycloak", "metadata": {"enabled": True}}

    assert UpsertBackendConfigInput(name="string", yaml_or_object=string_value).yaml_or_object == string_value
    assert UpsertBackendConfigInput(name="object", yaml_or_object=object_value).yaml_or_object == object_value
    assert UpsertBackendConfigInput(name="scalar", yaml_or_object=7).yaml_or_object == 7
    with pytest.raises(ValidationError):
        UpsertBackendConfigInput(name="invalid", yaml_or_object=object())


def test_authoring_error_is_successful_typed_outcome(tmp_path: Path) -> None:
    server, _ = _server(tmp_path, authoring=True)
    result = _tool(server, "auth.authoring.upsert_backend_config").fn(name="../escape", yaml_or_object={})
    assert result.ok and result.data.ok is False and result.data.error == "authoring_error"


def test_unclassified_adapter_errors_are_sanitized_failed_envelopes(tmp_path: Path) -> None:
    server, runtime = _server(tmp_path)

    class LeakyBackend:
        def verify_access_token(self, *args, **kwargs):
            return {"ok": False, "error": "remote secret=top-secret-token"}

    runtime._backend = LeakyBackend()
    result = _tool(server, "auth.verify_access_token").fn(token="secret-token")
    assert result.ok is False and result.data is None and result.error == "auth_backend_error"
    assert "secret" not in result.model_dump_json()


def test_thrown_backend_exception_is_sanitized_failed_envelope(tmp_path: Path) -> None:
    server, runtime = _server(tmp_path)

    class ExplodingBackend:
        def verify_access_token(self, *args, **kwargs):
            raise RuntimeError("remote secret=top-secret-token")

    runtime._backend = ExplodingBackend()
    result = _tool(server, "auth.verify_access_token").fn(token="secret-token")
    assert result.ok is False and result.data is None and result.error == "tool_execution_failed"
    assert "secret" not in result.model_dump_json()


def _minimal_args(name: str) -> dict[str, Any]:
    if name in {"auth.verify_access_token", "auth.introspect_token", "auth.revoke_token"}:
        return {"token": "x"}
    if name == "auth.refresh_token":
        return {"refresh_token": "x"}
    if name == "auth.get_user_info":
        return {"access_token": "x"}
    if name == "auth.exchange_token":
        return {"subject_token": "x", "subject_token_type": "access_token"}
    if name == "auth.authoring.upsert_backend_config":
        return {"name": "x", "yaml_or_object": {}}
    if name == "auth.authoring.delete_backend_config":
        return {"name": "x"}
    return {}
