"""Real composed #725 managed ToolInvocation lineage proof."""
from __future__ import annotations

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor

import pytest

from .managed_lineage_harness import LineageHarness


@pytest.fixture
def harness(tmp_path, monkeypatch) -> LineageHarness:
    return LineageHarness(tmp_path, monkeypatch)


def _assert_run(harness: LineageHarness, label: str, result: dict) -> None:
    from factory.mcp_server.runtime import graph_sink

    run_id = result["run_id"]
    attempt_id = result["attempt_id"]
    assert result["status"] == "succeeded"
    assert run_id.startswith("wfr:v1:")
    assert attempt_id.startswith("wfa:v1:")

    observed = harness.observed[label]
    assert observed["run_id"] == run_id
    assert observed["attributes"]["managed_graph.attempt_id"] == attempt_id
    assert graph_sink._current_workflow_run_id is None

    rows = harness.invocations(run_id)
    assert len(rows) == 1
    assert rows[0]["workflow_run_id"] == run_id
    assert rows[0]["brick_name"] == "probe"
    assert rows[0]["tool_name"] == "probe_record"
    assert json.loads(rows[0]["args_summary"])["label"] == label


def test_complete_managed_run_materializes_native_node_call(harness) -> None:
    _assert_run(harness, "a", harness.run("a"))


def test_two_complete_managed_runs_never_cross_ids(harness) -> None:
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = {label: pool.submit(harness.run, label) for label in ("a", "b")}
        results = {label: future.result(timeout=20) for label, future in futures.items()}

    assert results["a"]["run_id"] != results["b"]["run_id"]
    assert results["a"]["attempt_id"] != results["b"]["attempt_id"]
    for label in ("a", "b"):
        _assert_run(harness, label, results[label])

    assert harness.observed["a"]["run_id"] != harness.observed["b"]["run_id"]

    for label, other in (("a", "b"), ("b", "a")):
        tool = asyncio.run(harness.graph_server.get_tool("graph_get_run_topology"))
        topology = tool.fn(run_id=results[label]["run_id"])
        assert topology.ok and topology.data is not None
        node_ids = {node["id"] for node in topology.data.nodes}
        assert f"workflow-run-{results[label]['run_id']}" in node_ids
        assert {row["id"] for row in harness.invocations(results[label]["run_id"])} <= node_ids
        assert not ({row["id"] for row in harness.invocations(results[other]["run_id"])} & node_ids)


def test_native_gateway_binds_actual_and_fake_execution_providers(harness) -> None:
    from factory.workflow.runtime.canonical import canonical_loads

    actual = harness.run("binding")
    fake = harness.run_fake()
    fields = (
        "workflow_run_id", "attempt_id", "revision", "engine_id",
        "registration_digest", "request_digest", "provider_request_digest",
    )
    actual_attempt = harness.workflow_runtime.durable_storage.list_task_attempts(
        run_id=actual["run_id"]
    )[0]
    actual_output = canonical_loads(actual_attempt["output_json"])
    expected_actual = {
        "workflow_run_id": actual["run_id"], "attempt_id": actual["attempt_id"],
        "revision": actual["attempt_revision"], "engine_id": "langgraph",
        "registration_digest": actual["registration_digest"],
        "request_digest": actual["request_digest"],
        "provider_request_digest": actual["provider_request_digest"],
    }
    assert {field: actual_output[field] for field in fields} == expected_actual
    expected_fake = {
        "workflow_run_id": fake["run_id"], "attempt_id": fake["attempt_id"],
        "revision": 1, "engine_id": "fake_compute",
        "registration_digest": fake["registration_digest"],
        "request_digest": fake["request_digest"],
        "provider_request_digest": fake["provider_request_digest"],
    }
    assert {field: harness.fake_bindings[0][field] for field in fields} == expected_fake
    assert fake["status"] == "succeeded"
    for brick, tool in (("agent", "execute_langgraph_attempt"),
                        ("qa_fake", "execute_fake_compute_attempt")):
        denied = asyncio.run(harness.aggregator.call_brick_tool(brick, tool, {}))
        assert denied["ok"] is False
        assert denied["error"]["type"] == "ServiceOnlyAccessError"


def test_native_gateway_cancellation_uses_only_the_generic_owner_tuple(harness) -> None:
    from factory.mcp_server.runtime.native_invoker import NativeEnvelopeInvoker

    fake = harness.run_fake()
    fields = (
        "workflow_run_id", "attempt_id", "revision", "engine_id",
        "registration_digest", "request_digest", "provider_request_digest",
    )
    binding = {
        "workflow_run_id": fake["run_id"], "attempt_id": fake["attempt_id"],
        "revision": fake["attempt_revision"], "engine_id": "fake_compute",
        "registration_digest": fake["registration_digest"],
        "request_digest": fake["request_digest"],
        "provider_request_digest": fake["provider_request_digest"],
    }
    result = NativeEnvelopeInvoker(harness.aggregator).for_caller("workflow")(
        {"brick_name": "qa_fake", "tool_name": "cancel_fake_compute_attempt"},
        arguments=binding, idempotency_key=f"cancel:{binding['attempt_id']}:r1",
        envelope={"tenant_id": "tenant", "principal_id": "principal",
                  "run_id": binding["workflow_run_id"]},
        attempt=binding,
    )

    assert result["ok"] is True
    cancellation = harness.fake_bindings[-1]
    assert cancellation["cancel"] is True
    assert "request" not in cancellation
    assert {field: cancellation[field] for field in fields} == binding

    actual = harness.run("cancel")
    actual_binding = {
        "workflow_run_id": actual["run_id"],
        "attempt_id": actual["attempt_id"],
        "revision": actual["attempt_revision"],
        "engine_id": "langgraph",
        "registration_digest": actual["registration_digest"],
        "request_digest": actual["request_digest"],
        "provider_request_digest": actual["provider_request_digest"],
    }
    actual_result = NativeEnvelopeInvoker(harness.aggregator).for_caller("workflow")(
        {"brick_name": "agent", "tool_name": "cancel_langgraph_attempt"},
        arguments=actual_binding,
        idempotency_key=f"cancel:{actual_binding['attempt_id']}:r1",
        envelope={"run_id": actual_binding["workflow_run_id"]},
        attempt=actual_binding,
    )
    data = actual_result["result"]["structured_content"]["data"]
    assert data["engine_id"] == "langgraph"
    assert data["outcome"] == "not_found"
    assert "request" not in data
