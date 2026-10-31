from __future__ import annotations

import asyncio
import inspect
import yaml
import pytest

from factory.auth.interface import (
    LocalOpaqueWorkloadCredentialProvider, Runtime, WorkloadGrant,
)
from factory.auth.server import create_tool_catalog
from factory.mcp_utils.interface import (
    ServiceOnlyAccessError, get_service, is_service_only, reset_envelope,
    set_envelope, set_service, telemetry_projection,
)


class _AllowPolicy:
    def authorize(self, grant, *, tenant_id, audience):
        return grant if (grant.tenant_id, grant.audience) == (tenant_id, audience) else None


@pytest.fixture(autouse=True)
def _trusted_authority(monkeypatch):
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    previous = get_service("workload_grant_policy")
    set_service("workload_grant_policy", _AllowPolicy())
    token = set_envelope({"tenant_id": "tenant"})
    try:
        yield
    finally:
        reset_envelope(token)
        set_service("workload_grant_policy", previous)


def _catalog(tmp_path):
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    runtime = Runtime(
        tmp_path, workload_credentials=LocalOpaqueWorkloadCredentialProvider(),
    )
    return create_tool_catalog(runtime), runtime


def _arguments(generation=1, *, serialized=True):
    grant = WorkloadGrant.create(
        launch_id="launch", generation=generation, tenant_id="tenant",
        audience="companion-x", allowed_tools=["graph_get_entity"],
    )
    return {
        "workflow_run_id": "run", "attempt_id": "attempt", "revision": 0,
        "manifest_digest": grant.manifest_digest,
        "grant": grant.model_dump(mode="json") if serialized else grant,
    }


def _handler(catalog, name):
    tool = asyncio.run(catalog.get_tool(name))
    return inspect.unwrap(tool.fn)


def test_workload_tools_are_private_and_direct_call_has_zero_effect(tmp_path) -> None:
    catalog, _runtime = _catalog(tmp_path)
    issue = asyncio.run(catalog.get_tool("auth.issue_workload_credential"))
    revoke = asyncio.run(catalog.get_tool("auth.revoke_workload_credential"))
    assert is_service_only(issue) and is_service_only(revoke)
    from factory.mcp_server.runtime.service_policy import public_tool_map
    public = public_tool_map(catalog.tool_map())
    assert "auth.issue_workload_credential" not in public
    assert "auth.revoke_workload_credential" not in public
    with pytest.raises(ServiceOnlyAccessError):
        asyncio.run(catalog.call_tool("auth.issue_workload_credential", _arguments()))


def test_private_issue_duplicate_conflict_and_bound_revoke(tmp_path) -> None:
    catalog, runtime = _catalog(tmp_path)
    issue = _handler(catalog, "auth.issue_workload_credential")
    revoke = _handler(catalog, "auth.revoke_workload_credential")
    args = _arguments(serialized=False)
    first = issue(**args)
    private = first.data.credential
    assert private is not None
    access_token = private.access_token
    credential_id = private.credential.credential_id

    duplicate = issue(**args)
    assert duplicate.ok and duplicate.data.duplicate
    assert duplicate.data.credential is None
    assert duplicate.data.recovered_credential == private.credential
    conflict = issue(**_arguments(generation=2, serialized=False))
    assert not conflict.ok and conflict.error == "workload_attempt_manifest_conflict"
    assert access_token not in repr(duplicate) + repr(conflict)

    binding = {key: args[key] for key in (
        "workflow_run_id", "attempt_id", "revision", "manifest_digest")}
    denied = revoke(**{**binding, "attempt_id": "wrong",
                       "credential_id": credential_id})
    assert denied.ok and not denied.data.revoked
    assert runtime.workload_credentials.verify(access_token, "companion-x")
    revoked = revoke(**{**binding, "credential_id": credential_id})
    assert revoked.ok and revoked.data.revoked
    assert runtime.workload_credentials.verify(access_token, "companion-x") is None


def test_secret_projection_never_contains_access_token() -> None:
    canary = "secret-workload-token-canary"
    projected = telemetry_projection({
        "credential": {"credential_id": "id"}, "access_token": canary,
    }, protected=True)
    assert canary not in repr(projected)


def test_issue_fails_closed_without_policy_audience_or_matching_tenant(
    tmp_path, monkeypatch,
) -> None:
    catalog, runtime = _catalog(tmp_path)
    issue = _handler(catalog, "auth.issue_workload_credential")
    args = _arguments(serialized=False)
    set_service("workload_grant_policy", None)
    assert issue(**args).error == "workload_grant_denied"
    set_service("workload_grant_policy", _AllowPolicy())
    monkeypatch.delenv("MCP_AUTH_AUDIENCE")
    assert issue(**args).error == "workload_grant_denied"
    monkeypatch.setenv("MCP_AUTH_AUDIENCE", "companion-x")
    token = set_envelope({"tenant_id": "other"})
    try:
        assert issue(**args).error == "workload_grant_denied"
    finally:
        reset_envelope(token)
    assert runtime.workload_credentials._records == {}
