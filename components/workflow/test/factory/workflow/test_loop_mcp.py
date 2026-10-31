from __future__ import annotations

import asyncio

from factory.mcp_utils.interface import reset_envelope, set_envelope
from factory.workflow.mcp.loop_support import authority
from factory.workflow.server import create_mcp_server


def test_loop_authority_uses_ambient_identity_over_explicit() -> None:
    token = set_envelope({
        "tenant_id": "ambient-tenant", "principal_id": "ambient-owner",
        "session_id": "ambient-thread",
    })
    try:
        value = authority({
            "tenant_id": "forged-tenant", "principal_id": "forged-owner",
            "session_id": "forged-thread",
        })
    finally:
        reset_envelope(token)
    assert value.tenant_id == "ambient-tenant"
    assert value.principal_id == "ambient-owner"
    assert value.session_id == "ambient-thread"


def test_loop_authority_fills_only_missing_session_context() -> None:
    token = set_envelope({
        "tenant_id": "ambient-tenant", "principal_id": "ambient-owner",
    })
    try:
        value = authority({
            "tenant_id": "forged-tenant", "principal_id": "forged-owner",
            "session_id": "origin-thread",
        })
    finally:
        reset_envelope(token)
    assert value.tenant_id == "ambient-tenant"
    assert value.principal_id == "ambient-owner"
    assert value.session_id == "origin-thread"


def test_loop_authority_succeeds_with_no_session_id_at_all() -> None:
    """Real live bug (Agent Capabilities -> Projects tab): a page-level MCP
    call has no active chat turn, so the ambient envelope carries only
    tenant/principal — no session_id. ``authority()`` previously raised
    ``loop_owner_context_required`` for this, making ``workflow.list_loops``
    (and get_loop/get_loop_cycle/pause/resume/stop) permanently fail outside
    a chat turn. Reads never actually use session_id for anything; only
    ``start_loop`` does (validated separately, at that call site)."""
    token = set_envelope({"tenant_id": "page-tenant", "principal_id": "page-owner"})
    try:
        value = authority(None)
    finally:
        reset_envelope(token)
    assert value.tenant_id == "page-tenant"
    assert value.principal_id == "page-owner"
    assert value.session_id is None


def test_list_loops_works_without_a_chat_turn_session() -> None:
    """The exact reproduction of the live Projects-tab bug, at the runtime
    layer: list_loops must succeed for a caller with no session_id."""
    from factory.workflow.runtime.envelope import parse_envelope
    from factory.workflow.runtime.loop_runtime import LoopRuntime

    class _Runtime(LoopRuntime):
        def __init__(self) -> None:
            self.storage = None

        def _loop_store(self):
            class _Store:
                def list_loops(self, tenant, owner, limit):
                    return []
            return _Store()

    envelope = parse_envelope({"tenant_id": "page-tenant", "principal_id": "page-owner"})
    assert _Runtime().list_loops(envelope) == []


def test_start_loop_still_requires_a_resolvable_session() -> None:
    """The write path is unchanged: start_loop must still reject a
    session-less envelope (the relaxation only applies to reads)."""
    import pytest
    from factory.workflow.runtime.envelope import parse_envelope
    from factory.workflow.runtime.loop_runtime import LoopRuntime

    envelope = parse_envelope({"tenant_id": "page-tenant", "principal_id": "page-owner"})
    with pytest.raises(ValueError, match="loop_session_context_required"):
        LoopRuntime().start_loop(
            kind="goal", agent_id="developer", objective="x", cycle_instructions="y",
            interval_seconds=300, max_cycles=1, max_runtime_seconds=0,
            loop_id=None, origin_session_id="s1", envelope=envelope,
        )


def test_loop_mcp_has_no_public_settlement_tool() -> None:
    names = {tool.name for tool in asyncio.run(create_mcp_server().list_tools())}
    assert {
        "workflow.start_loop", "workflow.pause_loop", "workflow.resume_loop",
        "workflow.stop_loop", "workflow.get_loop", "workflow.list_loops",
        "workflow.get_loop_cycle",
    } <= names
    assert not any("settle_loop" in name or "report_loop" in name for name in names)
