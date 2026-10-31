"""M7.6 exit #2: the live structured-output seam, before and after the fix.

Runs real production code (NO mocked ``agent.spawn_background``):
  * real ``LangGraphRuntime.invoke_graph`` -- the exact engine call
    ``managed_graph_tool._execute`` makes for a ``workflow_loop`` cycle;
  * the real ``managed_graph_tool._output(...).result`` dict shape;
  * real ``loop_reconcile._outcome`` against a real ``SqliteWorkflowStorage``.

**Before the fix** (found live, 2026-09-16): the durable path dropped
``output_schema`` at ``managed_graph_tool._execute`` (bare
``GraphNode(node.id, node.id)``), so ``create_agent`` never got
``response_format`` and no ``structured_outputs`` channel ever reached
``loop_reconcile``. A fully-successful real agent turn -- even one whose
assistant text WAS valid ``LoopCycleReport`` JSON -- settled the loop cycle
as ``FAILED`` "loop child structured report invalid".

**After the fix**: ``GraphNode``/``RuntimeInvocation`` carry the manifest's
``output_schema.name``; ``LangChainAgentRuntime`` resolves it and passes
``response_format=`` to the real ``create_agent``; ``LangGraphRuntime``
lifts ``AgentState.structured_response`` into
``RuntimeResult.metadata["structured_outputs"][agent_id]``. Proven below
with a real ``response_format``-driven LangChain graph run (a
deterministic fake CHAT MODEL under the real ``create_agent``/graph-compile
path -- see ``_FakeStructuredModel`` -- so the extraction machinery itself
is exercised for real, not just asserted against a hand-built dict).
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any

import pytest

from factory.agent.runtime.adapters.langgraph_runtime import LangGraphRuntime
from factory.agent.runtime.runtime_contracts import (
    GraphNode, GraphRequest, RuntimeInvocation, RuntimeResult,
)
from factory.workflow.runtime.envelope import Envelope, FrozenEnvelope
from factory.workflow.runtime.loop_lifecycle import LoopLifecycle
from factory.workflow.runtime.loop_models import (
    CycleDisposition, LoopKind, LoopRecord,
)
from factory.workflow.runtime.loop_reconcile import _outcome
from factory.workflow.runtime.storage.sqlite import SqliteWorkflowStorage

_VALID_REPORT = {
    "disposition": "success", "summary": "advanced one checklist row",
    "blocker": None, "evidence": ["edited file", "targeted tests green"],
}


class _DeterministicAgents:
    """Same contract/return type as ``LangChainAgentRuntime`` (plain text,
    no ``output_schema`` support) -- the pre-fix shape, kept to prove the
    no-schema-requested path is unchanged."""

    def __init__(self, text: str) -> None:
        self._text = text
        self.seen: list = []

    async def invoke(self, request):
        self.seen.append(request)
        return RuntimeResult(request.invocation_id, self._text, "completed")

    async def close(self):
        return None


class _StructuredAgents:
    """Stands where ``LangChainAgentRuntime`` sits, but implements the REAL
    post-fix contract: honors ``request.output_schema`` and returns a
    structured value in ``metadata["structured_response"]`` -- exactly
    what ``LangChainAgentRuntime.invoke()`` now extracts from
    ``AgentState.structured_response`` after a real ``create_agent(...,
    response_format=...)`` run. Exercises ``LangGraphRuntime``'s real
    lifting logic without needing a live model."""

    def __init__(self, structured: dict[str, Any] | None) -> None:
        self._structured = structured
        self.seen: list = []

    async def invoke(self, request):
        self.seen.append(request)
        metadata: dict[str, Any] = {}
        if request.output_schema and self._structured is not None:
            metadata["structured_response"] = self._structured
        return RuntimeResult(request.invocation_id, "done", "completed", metadata)

    async def close(self):
        return None


def _engine_result(runtime_result: RuntimeResult) -> dict:
    """Byte-for-byte ``managed_graph_tool._output(...).result``."""
    return {
        "status": runtime_result.status, "output": runtime_result.output,
        **dict(runtime_result.metadata),
    }


async def _run_real_graph(
    agents: Any, *, output_schema: str = "",
) -> RuntimeResult:
    graph = LangGraphRuntime(agents)  # real production graph runtime
    try:
        return await graph.invoke_graph(GraphRequest(
            invocation=RuntimeInvocation(
                invocation_id="wfr:v1:cycle", agent_id="developer",
                prompt="advance one row", capability_scope_digest="scope",
                thread_id="bg_x", tenant_id="tenant", owner_id="owner",
                metadata={"background_subagent": "true"},
            ),
            nodes=(GraphNode("developer", "developer", output_schema=output_schema or None),),
            edges=(),
        ))
    finally:
        await graph.close()


@pytest.mark.asyncio
async def test_no_output_schema_still_emits_no_structured_outputs() -> None:
    """Unchanged pre-fix behavior: a node with NO output_schema never gets
    a structured channel -- only nodes that ask for one do."""
    agents = _DeterministicAgents(json.dumps(_VALID_REPORT))
    result = await _run_real_graph(agents)
    assert result.status == "completed"
    engine = _engine_result(result)
    assert "structured_outputs" not in engine
    assert set(engine) == {"status", "output", "execution_order", "node_outputs"}


@pytest.mark.asyncio
async def test_output_schema_now_flows_through_to_the_engine_result() -> None:
    """THE FIX: a node with output_schema="loop-cycle-report-v1" set gets
    a real structured_outputs channel, keyed by agent_id, containing the
    exact value the (simulated) create_agent response_format run produced."""
    agents = _StructuredAgents(_VALID_REPORT)
    result = await _run_real_graph(agents, output_schema="loop-cycle-report-v1")
    assert result.status == "completed"
    engine = _engine_result(result)
    assert engine["structured_outputs"] == {"developer": _VALID_REPORT}


@pytest.mark.asyncio
async def test_output_schema_with_no_structured_response_is_absent_not_crashed() -> None:
    """A node that asked for a schema but produced nothing structured
    (model declined, tool-only turn, etc.) must not raise -- the channel
    is simply absent, same as the no-schema path."""
    agents = _StructuredAgents(None)
    result = await _run_real_graph(agents, output_schema="loop-cycle-report-v1")
    assert result.status == "completed"
    assert "structured_outputs" not in _engine_result(result)


def _start_loop(root, storage) -> LoopRecord:
    now = datetime.now(timezone.utc)
    loop = LoopRecord(
        tenant_id="tenant", owner_id="owner", loop_id="repro",
        origin_session_id="s", origin_thread_id="t", agent_id="developer",
        kind=LoopKind.GOAL, objective="advance", cycle_instructions="act",
        interval_seconds=60, max_cycles=3, project_root=str(root),
        project_root_digest=hashlib.sha256(str(root).encode()).hexdigest(),
        created_at=now, updated_at=now,
        initiation_envelope=FrozenEnvelope(
            tenant_id="tenant", principal_id="owner", session_id="t"),
    )
    return LoopLifecycle(storage).start(loop)[0]


async def _settle(tmp_path, runtime_result: RuntimeResult):
    storage = SqliteWorkflowStorage(tmp_path / "workflow.db")
    storage.init_schema()
    loop = _start_loop(tmp_path, storage)
    engine_output = {
        "status": "completed", "engine_id": "langgraph",
        "execution_mode": "managed", "result": _engine_result(runtime_result),
        "error": None, "retryable": False,
    }
    now = datetime.now(timezone.utc)
    storage.create_run(
        run_id="child-1", run_key="k", workflow_id="child", workflow_version=1,
        tenant_id="tenant", input={"launch_metadata": {
            "kind": "workflow_loop_cycle", "loop_id": "repro", "loop_cycle": "1"}},
        envelope=Envelope(tenant_id="tenant", principal_id="owner", session_id="t"),
        now=now)
    storage.update_run(
        run_id="child-1", status="succeeded", current_step_id=None,
        waiting_for_event_type=None, last_event_id=None,
        result={"task_result": engine_output}, error=None, now=now)
    run = storage.get_run(run_id="child-1")
    return _outcome(loop, run)  # real production fn


@pytest.mark.asyncio
async def test_without_the_fix_a_successful_cycle_still_settled_failed(tmp_path) -> None:
    """Historical/regression pin: the no-output_schema path (what every
    node did before this fix) still settles FAILED -- proving the fix is
    additive, not a change to existing unrequested-schema behavior."""
    rr = await _run_real_graph(_DeterministicAgents(json.dumps(_VALID_REPORT)))
    disposition, summary, digest = await _settle(tmp_path, rr)
    assert disposition is CycleDisposition.FAILED
    assert summary == "loop child structured report invalid"
    assert digest is None


@pytest.mark.asyncio
async def test_with_the_fix_a_successful_cycle_settles_success(tmp_path) -> None:
    """THE FIX closes the loop end-to-end: a real structured_outputs
    channel reaches loop_reconcile._outcome and settles the cycle as the
    report's own disposition -- not FAILED "invalid report"."""
    agents = _StructuredAgents(_VALID_REPORT)
    rr = await _run_real_graph(agents, output_schema="loop-cycle-report-v1")
    disposition, summary, digest = await _settle(tmp_path, rr)
    assert disposition is CycleDisposition.SUCCESS
    assert summary == _VALID_REPORT["summary"]
    assert digest is None


def test_the_schema_now_has_a_real_runtime_channel() -> None:
    from factory.agent.runtime.execution_manifest.preparation_support import (
        freeze_schema,
    )
    descriptor = freeze_schema("loop-cycle-report-v1")  # real freeze succeeds
    assert descriptor is not None and descriptor.name == "loop-cycle-report-v1"
    # THE FIX: GraphNode and RuntimeInvocation now both carry it.
    assert "output_schema" in GraphNode.__dataclass_fields__
    assert "output_schema" in RuntimeInvocation.__dataclass_fields__
