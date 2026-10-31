from __future__ import annotations

from hypothesis import given, strategies as st
import pytest

from factory.auth.interface import (
    LocalOpaqueWorkloadCredentialProvider, WorkloadCredentialConflict,
    WorkloadGrant,
)
from factory.mcp_utils.interface import canonical_scope_digest


def _grant(**changes):
    base = WorkloadGrant.create(
        launch_id="launch-1", generation=1, tenant_id="tenant-1",
        audience="companion-x", allowed_tools=["graph_get_entity"],
    )
    if not changes:
        return base
    return WorkloadGrant(**{**base.model_dump(), **changes})


def test_public_helper_freezes_all_authority_fields() -> None:
    grant = WorkloadGrant.create(
        launch_id="launch-1", generation=2, tenant_id="tenant-1",
        audience="companion-x",
        allowed_tools=["memory_retrieve", "graph_get_entity"],
    )
    assert grant.allowed_tools == ["graph_get_entity", "memory_retrieve"]
    assert grant.policy_id == "workload:launch-1"
    assert grant.capability_scope_digest == canonical_scope_digest(
        grant.policy_id, grant.allowed_tools, 0)
    for field, value in [
        ("policy_id", "workload:other"),
        ("capability_scope_digest", "a" * 64),
        ("manifest_digest", "b" * 64),
        ("generation", 3),
        ("audience", "other"),
    ]:
        with pytest.raises(ValueError):
            WorkloadGrant(**{**grant.model_dump(), field: value})


def test_hash_only_exact_claims_expiry_revoke_and_restart() -> None:
    now = [1000.0]
    provider = LocalOpaqueWorkloadCredentialProvider(clock=lambda: now[0])
    issued = provider.issue(_grant(), workflow_run_id="run", attempt_id="a", revision=0)
    assert issued is not None and issued.access_token not in repr(provider.__dict__)
    assert provider.verify(issued.access_token, "companion-x") == issued.credential
    assert provider.verify(issued.access_token, "wrong") is None
    binding = dict(workflow_run_id="run", attempt_id="a", revision=0,
                   manifest_digest=_grant().manifest_digest)
    assert not provider.revoke(issued.credential.credential_id, **{
        **binding, "attempt_id": "wrong"})
    assert not provider.revoke("wrong-credential", **binding)
    assert not provider.revoke(issued.credential.credential_id, **{
        **binding, "manifest_digest": "0" * 64})
    assert provider.verify(issued.access_token, "companion-x") is not None
    assert provider.revoke(issued.credential.credential_id, **binding)
    assert provider.revoke(issued.credential.credential_id, **binding)
    assert provider.verify(issued.access_token, "companion-x") is None
    assert LocalOpaqueWorkloadCredentialProvider().verify(
        issued.access_token, "companion-x") is None


def test_duplicate_issue_is_secret_free_and_manifest_conflict_is_typed() -> None:
    provider = LocalOpaqueWorkloadCredentialProvider()
    args = dict(workflow_run_id="run", attempt_id="a", revision=0)
    issued = provider.issue(_grant(), **args)
    assert issued is not None
    recovered = provider.issue(_grant(), **args)
    assert recovered == issued.credential
    assert "access_token" not in repr(recovered)
    other = WorkloadGrant.create(
        launch_id="launch-1", generation=2, tenant_id="tenant-1",
        audience="companion-x", allowed_tools=["graph_get_entity"],
    )
    with pytest.raises(WorkloadCredentialConflict) as error:
        provider.issue(other, **args)
    assert issued.access_token not in repr(error.value)


@given(st.lists(st.sampled_from([
    "call_brick_tool", "auth_verify_access_token", "graph_*",
    "brick.graph", "graph_authoring_write", "graph_get_entity",
]), min_size=1, max_size=4))
def test_helper_never_accepts_forbidden_or_duplicate_names(names: list[str]) -> None:
    safe = len(names) == len(set(names)) and all(
        name == "graph_get_entity" for name in names)
    if safe:
        assert WorkloadGrant.create(
            launch_id="launch", generation=1, tenant_id="tenant",
            audience="companion-x", allowed_tools=names)
    else:
        with pytest.raises(ValueError):
            WorkloadGrant.create(
                launch_id="launch", generation=1, tenant_id="tenant",
                audience="companion-x", allowed_tools=names)


def test_runtime_verifier_recognizes_issuing_provider_instance() -> None:
    from factory.auth.access import RuntimeCredentialVerifier

    provider = LocalOpaqueWorkloadCredentialProvider()
    issued = provider.issue(_grant(), workflow_run_id="run", attempt_id="a", revision=0)
    assert issued is not None

    class Runtime:
        workload_credentials = provider

        def verify_access_token(self, **_kwargs):
            raise AssertionError("workload token must not reach user backend")

    verified = RuntimeCredentialVerifier(Runtime()).verify(
        issued.access_token, "companion-x")
    assert verified is not None
    assert verified["subject"] == "svc:squad:launch-1"
    assert verified["roles"] == ("workload",)
    assert verified["scopes"] == ("graph_get_entity",)


def test_local_opaque_provider_fails_closed_with_multiple_workers(monkeypatch) -> None:
    from factory.auth.server import get_workload_credential_provider

    monkeypatch.setenv("MCP_WORKLOAD_LOCAL_SINGLE_PROCESS", "true")
    monkeypatch.setenv("WEB_CONCURRENCY", "2")
    with pytest.raises(ValueError, match="exactly one worker"):
        get_workload_credential_provider()


class FakeExternalWorkloadProvider:
    """Test double for a remote authority implementing the public provider port."""
    def __init__(self, clock=lambda: 1000.0):
        self._authority = LocalOpaqueWorkloadCredentialProvider(clock=clock)

    def issue(self, grant, **binding):
        return self._authority.issue(grant, **binding)

    def verify(self, token, audience):
        return self._authority.verify(token, audience)

    def revoke(self, credential_id, **binding):
        return self._authority.revoke(credential_id, **binding)


@pytest.mark.parametrize("provider_factory", [
    LocalOpaqueWorkloadCredentialProvider, FakeExternalWorkloadProvider,
], ids=["local", "fake-external"])
def test_provider_issue_verify_duplicate_revoke_conformance(provider_factory) -> None:
    provider = provider_factory()
    binding = dict(workflow_run_id="run", attempt_id="attempt", revision=0)
    issued = provider.issue(_grant(), **binding)
    assert issued.access_token
    assert provider.verify(issued.access_token, "companion-x") == issued.credential
    recovered = provider.issue(_grant(), **binding)
    assert recovered == issued.credential
    assert "access_token" not in repr(recovered)
    assert provider.revoke(
        recovered.credential_id, **binding,
        manifest_digest=recovered.manifest_digest,
    )
    assert provider.verify(issued.access_token, "companion-x") is None


@pytest.mark.parametrize("offset,valid", [(-1, True), (0, False), (1, False)])
def test_expiry_boundary_t_minus_one_t_and_t_plus_one(offset: int, valid: bool) -> None:
    now = [1000.0]
    provider = LocalOpaqueWorkloadCredentialProvider(clock=lambda: now[0])
    issued = provider.issue(_grant(), workflow_run_id="run", attempt_id="a", revision=0)
    now[0] = issued.credential.expires_at + offset
    assert (provider.verify(issued.access_token, "companion-x") is not None) is valid


def test_server_composition_injects_same_provider_into_issuer_and_verifier(
    tmp_path, monkeypatch,
) -> None:
    import yaml
    from factory.auth.access import create_credential_verifier
    from factory.auth.server import get_runtime
    (tmp_path / "backends").mkdir()
    (tmp_path / "settings.yaml").write_text(yaml.safe_dump({
        "service_name": "test", "backend": "memory"}))
    (tmp_path / "backends" / "memory.yaml").write_text("kind: memory\n")
    monkeypatch.setenv("AUTH_CONFIG_DIR", str(tmp_path))
    provider = FakeExternalWorkloadProvider()
    issuer_runtime = get_runtime(workload_credential_provider=provider)
    verifier = create_credential_verifier(workload_credential_provider=provider)
    assert issuer_runtime.workload_credentials is provider
    assert verifier.runtime.workload_credentials is provider


def test_local_provider_requires_explicit_single_process_mode(monkeypatch) -> None:
    from factory.auth.server import get_workload_credential_provider

    monkeypatch.delenv("MCP_WORKLOAD_LOCAL_SINGLE_PROCESS", raising=False)
    provider = get_workload_credential_provider()
    assert provider.verify("unknown", "companion-x") is None
    with pytest.raises(RuntimeError, match="not configured"):
        provider.issue(_grant(), workflow_run_id="run", attempt_id="a", revision=0)
