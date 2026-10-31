from __future__ import annotations

import pytest

from factory.auth.interface import WorkloadGrant
from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.workflow.runtime.workload_lifecycle import (
    WorkloadAttemptRecoveryError, WorkloadLaunchManifest,
    WorkloadLifecycleCoordinator,
)


class Invoker:
    def __init__(self, events=None, issue_error=False):
        self.calls, self.events, self.issue_error = [], events if events is not None else [], issue_error

    def __call__(self, target, **kwargs):
        self.calls.append((target, kwargs))
        if "issue" in target["tool_name"]:
            self.events.append("issue")
            structured = ({
                "schema_version": "v1", "ok": True,
                "data": {"issued": True, "duplicate": False, "credential": {
                    "access_token": "host-secret-token",
                    "credential": {"credential_id": "credential-1"},
                }}, "error": None, "idempotency_key": None,
            } if not self.issue_error else {
                "schema_version": "v1", "ok": False, "data": None,
                "error": "issue_failed", "idempotency_key": None,
            })
        else:
            self.events.append("revoke")
            structured = {
                "schema_version": "v1", "ok": True,
                "data": {"revoked": True}, "error": None,
                "idempotency_key": None,
            }
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": structured,
        }}


class Activator:
    def __init__(self, events=None, fail=False):
        self.fail, self.seen, self.closed = fail, None, []
        self.events = events if events is not None else []

    async def activate(self, manifest, access_token):
        self.events.append("activate")
        self.seen = access_token
        if self.fail:
            raise RuntimeError("activation failed")
        return "unix:///run/workloads/launch.sock"

    async def deactivate(self, endpoint):
        self.events.append("deactivate")
        self.closed.append(endpoint)


def _grant():
    return WorkloadGrant.create(
        launch_id="launch", generation=1, tenant_id="tenant",
        audience="companion-x", allowed_tools=["graph_get_entity"],
    )


def _manifest():
    grant = _grant()
    return WorkloadLaunchManifest(
        workflow_run_id="run", attempt_id="attempt", revision=0,
        manifest_digest=grant.manifest_digest, grant=grant,
        authority_tenant_id="tenant",
    )


async def _trusted_launch(coordinator, manifest):
    token = set_envelope({"tenant_id": "tenant", "principal_id": "workflow"})
    try:
        return await coordinator.launch(manifest)
    finally:
        reset_envelope(token)


@pytest.mark.asyncio
async def test_real_native_shape_and_revoke_precedes_deactivate() -> None:
    events = []
    invoker, activator = Invoker(events), Activator(events)
    coordinator = WorkloadLifecycleCoordinator(invoker, activator)
    lease = await _trusted_launch(coordinator, _manifest())
    assert activator.seen == "host-secret-token"
    assert "host-secret-token" not in repr(lease)
    assert invoker.calls[0][1]["attempt"] == _manifest().attempt_binding
    await coordinator.close(lease)
    assert events == ["issue", "activate", "revoke", "deactivate"]
    assert activator.closed == [lease.endpoint]


@pytest.mark.asyncio
async def test_activation_failure_compensates_with_revoke() -> None:
    events = []
    invoker = Invoker(events)
    coordinator = WorkloadLifecycleCoordinator(invoker, Activator(events, fail=True))
    with pytest.raises(RuntimeError, match="activation failed") as error:
        await _trusted_launch(coordinator, _manifest())
    assert events == ["issue", "activate", "revoke"]
    assert "host-secret-token" not in repr(error.value)


@pytest.mark.asyncio
async def test_revoke_failure_still_deactivates() -> None:
    events = []
    invoker, activator = Invoker(events), Activator(events)
    coordinator = WorkloadLifecycleCoordinator(invoker, activator)
    lease = await _trusted_launch(coordinator, _manifest())
    original = invoker.__call__

    def fail_revoke(target, **kwargs):
        if "revoke" in target["tool_name"]:
            events.append("revoke")
            return {"ok": False, "error": "transport"}
        return original(target, **kwargs)

    coordinator._invoke = fail_revoke
    with pytest.raises(RuntimeError, match="revoke failed"):
        await coordinator.close(lease)
    assert events[-2:] == ["revoke", "deactivate"]


def test_manifest_requires_validated_frozen_grant_not_mapping() -> None:
    grant = _grant()
    with pytest.raises(TypeError, match="frozen WorkloadGrant"):
        WorkloadLaunchManifest(
            "run", "attempt", 0, grant.manifest_digest,
            {"manifest_digest": grant.manifest_digest}, "tenant",  # type: ignore[arg-type]
        )


@pytest.mark.asyncio
async def test_mutated_grant_is_revalidated_before_issue() -> None:
    manifest = _manifest()
    manifest.grant.allowed_tools.append("memory_retrieve")
    coordinator = WorkloadLifecycleCoordinator(Invoker(), Activator())
    with pytest.raises(ValueError, match="sorted|manifest|scope"):
        await _trusted_launch(coordinator, manifest)


@pytest.mark.asyncio
async def test_duplicate_recovery_is_revoked_immediately_and_requires_new_attempt() -> None:
    events = []

    class DuplicateInvoker(Invoker):
        def __call__(self, target, **kwargs):
            if "issue" not in target["tool_name"]:
                return super().__call__(target, **kwargs)
            self.calls.append((target, kwargs))
            self.events.append("issue")
            structured = {
                "schema_version": "v1", "ok": True,
                "data": {"issued": False, "duplicate": True, "credential": None,
                         "recovered_credential": {"credential_id": "recovered-1"}},
                "error": None, "idempotency_key": None,
            }
            return {"ok": True, "result": {"kind": "tool", "content": [],
                    "meta": {}, "structured_content": structured}}

    invoker = DuplicateInvoker(events)
    activator = Activator(events)
    coordinator = WorkloadLifecycleCoordinator(invoker, activator)
    with pytest.raises(WorkloadAttemptRecoveryError, match="new attempt") as error:
        await _trusted_launch(coordinator, _manifest())
    assert events == ["issue", "revoke"]
    assert activator.seen is None
    assert "recovered-1" not in str(error.value)
