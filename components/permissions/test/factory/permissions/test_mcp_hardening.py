"""Public FastMCP regressions for Permissions transport hardening."""
from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.permissions.runtime.audit import InMemoryAuditStore
from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.server import create_mcp_server


def _call(server: Any, name: str, arguments: dict[str, Any]) -> Any:
    return asyncio.run(server.call_tool(name, arguments))


class FakeRuntime:
    _settings = None

    def __init__(self, result: dict[str, Any]):
        self._config_dir = Path(".")
        self.result = result
        self.calls: list[tuple[str, Any]] = []

    def get_capabilities(self) -> dict[str, Any]:
        return {"schema_version": 1, "tools": {"deterministic": [], "operational": []}}

    def get_policies(self) -> list[Any]:
        return []

    def get_role_registry(self) -> list[dict[str, Any]]:
        return []

    def evaluate(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("evaluate", kwargs["envelope"]))
        return dict(self.result)

    def batch_evaluate(self, **kwargs: Any) -> list[dict[str, Any]]:
        self.calls.append(("batch", kwargs["envelope"]))
        return [dict(self.result)]

    def explain(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(("explain", kwargs["envelope"]))
        return dict(self.result)


def _request() -> dict[str, Any]:
    return {"action": "read", "resource": {"type": "document", "id": "doc-1"}}


def test_timestamp_schema_and_public_raw_kwargs_accept_rfc3339(tmp_path: Path) -> None:
    server = create_mcp_server(PermissionsRuntime(tmp_path))
    tool = asyncio.run(server.get_tool("permissions.evaluate"))
    timestamp = tool.fn._mcp_input_model.model_json_schema(mode="validation")[
        "$defs"
    ]["EnvelopeInput"]["properties"]["timestamp"]
    assert timestamp["anyOf"][0]["format"] == "date-time"

    result = _call(server, "permissions.evaluate", {
        **_request(), "envelope": {"timestamp": "2026-08-20T00:00:00Z"},
    })
    assert result.structured_content["ok"] is True

    native = _call(server, "permissions.evaluate", {
        **_request(), "envelope": {"timestamp": datetime(2026, 8, 20, tzinfo=timezone.utc)},
    })
    assert native.structured_content["ok"] is True


@pytest.mark.parametrize("timestamp", [1700000000, "2026-08-20", "2026-08-20T00:00:00"])
def test_public_raw_kwargs_reject_non_timezone_timestamps(tmp_path: Path, timestamp: object) -> None:
    server = create_mcp_server(PermissionsRuntime(tmp_path))
    with pytest.raises(Exception, match="validation failed"):
        _call(server, "permissions.evaluate", {**_request(), "envelope": {"timestamp": timestamp}})


def test_public_evidence_normalization_preserves_yaml_aws_and_cedar(tmp_path: Path) -> None:
    cases = [
        ({"decision": "allow", "determining_policies": [{"policy_id": "yaml-p", "rule_id": "r1", "effect": "allow"}]}, "yaml-p"),
        ({"decision": "allow", "determining_policies": [{"policyId": "aws-p"}], "errors": [{"errorDescription": "secret/provider/path"}]}, "aws-p"),
        ({"decision": "deny", "determining_policies": ["cedar-p"], "diagnostics": ["raw provider secret" ]}, "cedar-p"),
    ]
    for result_data, policy_id in cases:
        runtime = FakeRuntime(result_data)
        result = _call(create_mcp_server(runtime), "permissions.evaluate", _request())
        payload = result.structured_content
        assert payload["ok"] is True
        assert payload["data"]["determining_policies"][0]["policy_id"] == policy_id
        assert "secret/provider/path" not in str(payload)
        assert "raw provider secret" not in str(payload)


def test_public_batch_and_explain_accept_backend_evidence_shapes() -> None:
    runtime = FakeRuntime({
        "decision": "allow",
        "determining_policies": [{"policyId": "aws-p"}],
        "matched_rules": ["aws-p"],
        "diagnostics": ["cedar diagnostic"],
        "errors": [{"errorDescription": "provider detail"}],
    })
    server = create_mcp_server(runtime)
    batch = _call(server, "permissions.batch_evaluate", {"requests": [_request()]})
    explain = _call(server, "permissions.explain", _request())
    assert batch.structured_content["ok"] is True
    assert batch.structured_content["data"]["decisions"][0]["determining_policies"][0]["policy_id"] == "aws-p"
    assert explain.structured_content["ok"] is True
    assert explain.structured_content["data"]["matched_rules"][0]["policy_id"] == "aws-p"
    assert explain.structured_content["data"]["errors"] == [{"code": "provider_error"}]


def test_unknown_evidence_is_a_safe_failed_tool_result() -> None:
    runtime = FakeRuntime({"decision": "allow", "determining_policies": [{"secret": "do-not-leak"}]})
    result = _call(create_mcp_server(runtime), "permissions.evaluate", _request())
    payload = result.structured_content
    assert payload["ok"] is False
    assert payload["data"] is None
    assert payload["error"] == "tool_execution_failed"
    assert "do-not-leak" not in str(payload)


def test_trusted_context_wins_for_evaluate_batch_explain_and_audit(tmp_path: Path) -> None:
    runtime = FakeRuntime({"decision": "allow"})
    server = create_mcp_server(runtime)
    token = set_envelope({
        "principal_id": "trusted-principal", "tenant_id": "trusted-tenant",
        "attributes": {"scope": "trusted"},
    })
    try:
        public = {**_request(), "envelope": {
            "principal_id": "public-principal", "tenant_id": "public-tenant",
            "attributes": {"scope": "public", "untrusted": "value"},
        }}
        assert _call(server, "permissions.evaluate", public).structured_content["ok"] is True
        assert _call(server, "permissions.batch_evaluate", {"requests": [_request()], "envelope": public["envelope"]}).structured_content["ok"] is True
        assert _call(server, "permissions.explain", public).structured_content["ok"] is True
    finally:
        reset_envelope(token)
    assert all(env.principal_id == "trusted-principal" for _, env in runtime.calls)
    assert all(env.tenant_id == "trusted-tenant" for _, env in runtime.calls)
    assert all(env.attributes == {"scope": "trusted"} for _, env in runtime.calls)

    (tmp_path / "policies").mkdir()
    real_runtime = PermissionsRuntime(tmp_path)
    audit = InMemoryAuditStore()
    real_runtime.set_audit_store(audit)
    token = set_envelope({"principal_id": "audit-principal", "tenant_id": "audit-tenant"})
    try:
        result = _call(create_mcp_server(real_runtime), "permissions.evaluate", {
            **_request(), "envelope": {"principal_id": "forged", "tenant_id": "forged"},
        })
    finally:
        reset_envelope(token)
    assert result.structured_content["ok"] is True
    entry = audit.list()[0]
    assert entry.principal_id == "audit-principal"
    assert entry.tenant_id == "audit-tenant"


def test_no_trusted_context_keeps_validated_public_identity() -> None:
    runtime = FakeRuntime({"decision": "deny"})
    result = _call(create_mcp_server(runtime), "permissions.evaluate", {
        **_request(), "envelope": {"principal_id": "public", "tenant_id": "tenant"},
    })
    assert result.structured_content["ok"] is True
    assert runtime.calls[0][1].principal_id == "public"
    assert runtime.calls[0][1].tenant_id == "tenant"
