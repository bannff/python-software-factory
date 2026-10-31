"""Fresh S2 MCP canary: exactly four supervision verbs on the ML surface.

The verbs are @operational (owner-actionable bridge, never @deterministic)
and surface typed supervision failures as ToolResult fail envelopes, never
raw exceptions.
"""
from __future__ import annotations

import asyncio

from factory.machine_learning.server import create_mcp_server
from factory.machine_learning.runtime.adapters.local_can_lifecycle import (
    LocalCanLifecycleStore,
)
from factory.machine_learning.runtime.can_lifecycle_identity import TRAIN_OPERATION
from factory.machine_learning.runtime.supervision_claims import (
    TrainingSupervision, adjusted_child_id,
)
from factory.mcp_utils.interface import ToolResult

_OP = TRAIN_OPERATION


def _fixture(tmp_path) -> tuple[LocalCanLifecycleStore, object]:
    store = LocalCanLifecycleStore(tmp_path)
    claim, _ = store.claim(_OP, "live", "b" * 64)
    assert claim == "created"
    return store, TrainingSupervision(store)


def test_supervision_tools_dispatch_and_fail_loudly(tmp_path) -> None:
    """Four verbs registered; typed errors become fail envelopes, not raises."""
    store, service = _fixture(tmp_path)
    server = create_mcp_server(supervision_service=service)
    names = ("ml_pause_training", "ml_stop_at_checkpoint",
             "ml_adjust_hyperparam", "ml_resume_training")
    tools = {name: asyncio.run(server.get_tool(name)) for name in names}
    for name in names:
        assert tools[name] is not None, name
    ok = tools["ml_pause_training"].fn(attempt_id="live", reason="drift")
    assert isinstance(ok, ToolResult) and ok.ok
    assert ok.data.status == "pending" and ok.data.operation == _OP
    fail_now = tools["ml_resume_training"].fn(attempt_id="ghost")
    assert fail_now.ok is False and fail_now.data is None
    assert "unknown supervised attempt" in fail_now.error
    inspect: str = "ml_stop_at_checkpoint"
    stopped = tools[inspect].fn(attempt_id="live", checkpoint_name="ck1")
    assert stopped.ok and stopped.data.action == "stop"


def test_supervision_envelopes_are_terminal_and_adjust_aware(tmp_path) -> None:
    """Adjust verb mints a child claim; unknown attempt fails loudly."""
    store, service = _fixture(tmp_path)
    server = create_mcp_server(supervision_service=service)
    adjust = asyncio.run(server.get_tool("ml_adjust_hyperparam"))
    result = adjust.fn(attempt_id="live", hyperparams={"epochs": 4})
    assert result.ok and result.data.status == "minted"
    assert result.data.parent_attempt_id == "live"
    assert adjust.fn(attempt_id="ghost", hyperparams={"epochs": 4}).ok is False


def test_adjust_conflict_maps_to_typed_fail_envelope(tmp_path) -> None:
    """A pre-bound adjusted attempt key yields the typed conflict envelope.

    The runtime conflict dict is terminal-negative data: the tool layer must
    map it to ``fail`` (S1 terminal convention) rather than let it die inside
    ``AdjustedClaimOutput`` validation and surface ``tool_execution_failed``.
    """
    store, service = _fixture(tmp_path)
    parent = store.load(_OP, "live")
    child_id = adjusted_child_id(_OP, parent, {"epochs": 4})
    claim, _ = store.claim(_OP, child_id, "d" * 64)
    assert claim == "created"
    server = create_mcp_server(supervision_service=service)
    adjust = asyncio.run(server.get_tool("ml_adjust_hyperparam"))
    conflict = adjust.fn(attempt_id="live", hyperparams={"epochs": 4})
    assert conflict.ok is False and conflict.data is None
    assert "already bound to a different request" in conflict.error
    assert conflict.error != "tool_execution_failed"



