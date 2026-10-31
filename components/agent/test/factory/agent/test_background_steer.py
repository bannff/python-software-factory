from __future__ import annotations

from types import SimpleNamespace

import pytest

from factory.agent.runtime.background import steer as module
from factory.agent.runtime.background.launch import BackgroundLaunchError
from factory.mcp_utils.interface import reset_envelope, set_envelope


@pytest.mark.asyncio
async def test_background_steer_returns_truthful_written_state(monkeypatch) -> None:
    async def call(*args, **kwargs):
        return {"status": "running", "initiation_envelope": {"principal_id": "owner"},
                "input": {"launch_metadata": {
            "kind": "background_subagent",
        }}}

    async def offer(run_id, send_id, content):
        assert (run_id, send_id, content) == ("run:1", "send-1", "redirect")
        return SimpleNamespace(send_id=send_id, revision=1)

    monkeypatch.setattr(module, "_call", call)
    monkeypatch.setattr(module.managed_steering, "offer", offer)
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        result = await module.steer_background("run:1", "send-1", "redirect")
    finally:
        reset_envelope(token)
    assert result == {
        "run_id": "run:1", "send_id": "send-1",
        "state": "written", "revision": 1,
    }


@pytest.mark.asyncio
async def test_background_steer_never_claims_inactive_delivery(monkeypatch) -> None:
    async def call(*args, **kwargs):
        return {"status": "succeeded", "initiation_envelope": {"principal_id": "owner"},
                "input": {"launch_metadata": {
            "kind": "background_subagent",
        }}}

    async def inactive(*args):
        return None

    monkeypatch.setattr(module, "_call", call)
    monkeypatch.setattr(module.managed_steering, "offer", inactive)
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner"})
    try:
        with pytest.raises(BackgroundLaunchError) as error:
            await module.steer_background("run:1", "send-2", "late")
    finally:
        reset_envelope(token)
    assert error.value.code == "background_not_running"


@pytest.mark.asyncio
async def test_background_steer_denies_same_tenant_foreign_owner(monkeypatch) -> None:
    async def call(*args, **kwargs):
        return {
            "initiation_envelope": {"principal_id": "owner-a"},
            "input": {"launch_metadata": {"kind": "background_subagent"}},
        }

    monkeypatch.setattr(module, "_call", call)
    token = set_envelope({"tenant_id": "tenant", "principal_id": "owner-b"})
    try:
        with pytest.raises(BackgroundLaunchError) as error:
            await module.steer_background("run:1", "send-foreign", "redirect")
    finally:
        reset_envelope(token)
    assert error.value.code == "background_run_not_found"
