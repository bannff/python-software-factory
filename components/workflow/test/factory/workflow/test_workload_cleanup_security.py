from __future__ import annotations

import pytest

from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.workflow.runtime.workload_lifecycle import WorkloadLifecycleCoordinator

from .test_workload_lifecycle import Activator, Invoker, _manifest, _trusted_launch


@pytest.mark.asyncio
async def test_false_revoke_is_cleanup_failure_and_still_deactivates() -> None:
    events = []
    invoker, activator = Invoker(events), Activator(events)
    coordinator = WorkloadLifecycleCoordinator(invoker, activator)
    lease = await _trusted_launch(coordinator, _manifest())

    def false_revoke(target, **_kwargs):
        assert "revoke" in target["tool_name"]
        events.append("revoke")
        return {"ok": True, "result": {
            "kind": "tool", "content": [], "meta": {},
            "structured_content": {
                "schema_version": "v1", "ok": True,
                "data": {"revoked": False}, "error": None,
                "idempotency_key": None,
            },
        }}

    coordinator._invoke = false_revoke
    with pytest.raises(RuntimeError, match="revoke failed"):
        await coordinator.close(lease)
    assert events[-2:] == ["revoke", "deactivate"]


@pytest.mark.asyncio
async def test_launch_rejects_missing_or_mismatched_ambient_tenant() -> None:
    coordinator = WorkloadLifecycleCoordinator(Invoker(), Activator())
    with pytest.raises(ValueError, match="tenant authority"):
        await coordinator.launch(_manifest())
    token = set_envelope({"tenant_id": "other", "principal_id": "workflow"})
    try:
        with pytest.raises(ValueError, match="tenant authority"):
            await coordinator.launch(_manifest())
    finally:
        reset_envelope(token)
