"""Generic execution-event journal fencing and service boundary tests."""
from __future__ import annotations

import hashlib
import threading
from pathlib import Path

import pytest
from factory.mcp_utils.interface import (ExecutionBinding, ServiceOnlyAccessError,
    acquire_service_entry, begin_service_invocation, end_service_invocation,
    mint_internal_invocation_claims, reset_internal_invocation_claims,
    set_internal_invocation_claims)
from factory.workflow.mcp.contracts.operational import AppendExecutionEventInput
from factory.workflow.mcp.execution import register
from factory.workflow.runtime.canonical import canonical_json, canonical_loads
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .test_managed_graph import DIGEST, GraphInvoker, runtime, start


class BlockingInvoker(GraphInvoker):
    def __init__(self) -> None:
        super().__init__(); self.started, self.release = threading.Event(), threading.Event()

    def invoke(self, **kwargs):
        if kwargs["target"].tool_name == "cancel_strands_graph_attempt":
            return super().invoke(**kwargs)
        self.started.set(); assert self.release.wait(timeout=5)
        return super().invoke(**kwargs)


def _launch(tmp_path: Path, key: str = "key"):
    root = tmp_path / key; root.mkdir(); invoker = BlockingInvoker(); owner = runtime(root, invoker)
    result, errors = {}, []
    thread = threading.Thread(target=lambda: _run(owner, result, errors, key)); thread.start()
    assert invoker.started.wait(timeout=5)
    record = owner.durable_storage.get_run_by_key(run_key=key)
    return owner, invoker, thread, result, errors, record, owner.durable_storage.list_task_attempts(run_id=record.run_id)[0]


def _run(owner, result, errors, key):
    try: result.update(start(owner, run_key=key))
    except BaseException as exc: errors.append(exc)


def _values(record, attempt, sequence, raw, terminal=False, **changes):
    values = {"workflow_run_id": record.run_id, "attempt_id": attempt["attempt_id"],
      "revision": attempt["revision"], "engine_id": "strands_graph",
      "registration_digest": canonical_loads(attempt.get("input_json", canonical_json(attempt.get("input", {}))))["registration_digest"],
      "request_digest": canonical_loads(attempt.get("input_json", canonical_json(attempt.get("input", {}))))["request_digest"],
      "provider_request_digest": DIGEST, "sequence": sequence, "terminal": terminal,
      "raw_evidence": raw, "safe_metadata": {"native_event_type": "node"}}
    values.update(changes); return values


def _append(owner, record, attempt, sequence, raw, terminal=False, **changes):
    return owner.append_execution_event(**_values(record, attempt, sequence, raw, terminal, **changes))


def _finish(invoker, thread, errors):
    invoker.release.set(); thread.join(timeout=5); assert not thread.is_alive() and not errors


def test_contract_enforces_safe_metadata_limits() -> None:
    base = _values(type("R", (), {"run_id":"run"})(), {"attempt_id":"a", "revision":1,
      "input":{"registration_digest":"a"*64,"request_digest":"b"*64}}, 0, {})
    with pytest.raises(ValueError, match="safe_metadata"):
        AppendExecutionEventInput.model_validate({**base, "safe_metadata": {"x"*33:"v"}})


def test_journal_contiguity_terminal_and_generic_retrieval(tmp_path):
    owner, invoker, thread, _, errors, record, attempt = _launch(tmp_path)
    first, terminal = {"type":"node", "value":1}, {"type":"done"}
    assert _append(owner, record, attempt, 0, first)["appended"]
    assert not _append(owner, record, attempt, 0, first)["appended"]
    with pytest.raises(ValueError, match="conflict"): _append(owner, record, attempt, 0, {"value":2})
    assert _append(owner, record, attempt, 1, terminal, terminal=True)["appended"]
    with pytest.raises(ValueError, match="follows terminal"): _append(owner, record, attempt, 2, first)
    rows = owner.get_execution_events(workflow_run_id=record.run_id)
    assert [row["sequence"] for row in rows] == [0, 1]
    assert [row["raw_evidence"] for row in rows] == [first, terminal]
    assert rows[-1]["terminal"] and rows[0]["raw_digest"] == hashlib.sha256(canonical_json(first).encode()).hexdigest()
    _finish(invoker, thread, errors)


async def _protected_append(mcp, values):
    name = "workflow.append_execution_event"; tool = await mcp.get_tool(name)
    binding = ExecutionBinding(**{key: values[key] for key in ("workflow_run_id", "attempt_id", "revision", "engine_id", "registration_digest", "request_digest", "provider_request_digest")})
    token = set_internal_invocation_claims(mint_internal_invocation_claims(caller="agent", audience="workflow", target_tool=name, binding=binding, target=tool)); state = None
    try:
        state = begin_service_invocation(tool, audience="workflow", target_tool=name, arguments=values)
        return await mcp.call_tool(name, {
            **values, "_service_entry_authorization": acquire_service_entry(tool.fn),
        })
    finally:
        end_service_invocation(state); reset_internal_invocation_claims(token)


@pytest.mark.asyncio
async def test_private_append_accepts_execution_claim_and_denies_public(tmp_path):
    owner, invoker, thread, _, errors, record, attempt = _launch(tmp_path)
    mcp = ToolCatalog("workflow-events"); register(mcp, owner); values = _values(record, attempt, 0, {"type":"node"})
    with pytest.raises(Exception, match="ServiceOnlyAccessError|service-only boundary|Failed to resolve dependency"): await mcp.call_tool("workflow.append_execution_event", values)
    assert (await _protected_append(mcp, values)).structured_content["data"]["appended"]
    _finish(invoker, thread, errors)
