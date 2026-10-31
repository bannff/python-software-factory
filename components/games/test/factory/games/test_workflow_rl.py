from __future__ import annotations

from unittest.mock import patch

from factory.games.runtime.workflow_rl import process_workflow_rl
from factory.mcp_utils.interface import ToolResult


def _patch_invoker(monkeypatch, fake_invoker, gt_loader=lambda app: []):
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._get_invoker",
        lambda: fake_invoker,
    )
    monkeypatch.setattr(
        "factory.games.runtime.workflow_rl._load_gt", gt_loader,
    )


def test_process_workflow_rl_plans_reward_and_learning_without_side_effects(monkeypatch) -> None:
    calls: list[str] = []

    def fake_invoker(tool_name: str, **kwargs):
        calls.append(tool_name)
        if tool_name == "graph_graph_query":
            return {"raw": [{"n": {"agent_id": "agent-1", "cwe_id": "CWE-639",
                                   "method": "GET", "path": "/api/users/1"}}]}
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"precision": 0.8, "recall": 0.84, "f1": 0.82,
                                    "true_positives": 4, "false_positives_count": 1,
                                    "false_negatives": 2})
        if tool_name == "evals_evals_persist_score":
            return {"persisted": True, "doc_id": f"eval-{kwargs['run_id']}"}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   lambda app: [{"cwe_id": "CWE-639", "method": "GET", "path": "/api/users/1"}])

    result = process_workflow_rl(
        graph_id="rt-scan-idor",
        run_id="run-WebGoat-123",
        vuln_class="IDOR",
        workflow_type="dast",
        target_app="WebGoat",
    )

    assert result["scoring"]["f1"] == 0.82
    assert result["blockchain"] == {
        "eligible": True, "amount": 82.0,
        "wallet_id": "wallet-kiro-agent", "status": "pending_event",
    }
    assert result["memory"]["stored"] is False
    assert result["memory"]["status"] == "pending_event"
    assert result["memory"]["summary_type"] == "workflow_rl"
    assert "blockchain_mint" not in calls
    assert "memory_memory_store" not in calls
    # The y9tq unification: persist via evals MCP, not the deleted edge writer.
    assert "evals_evals_persist_score" in calls
    assert "graph_graph_add_relationship" not in calls


@patch("factory.games.runtime.workflow_rl.event_emitter.emit")
@patch("factory.games.runtime.workflow_rl._plan_learning")
@patch("factory.games.runtime.workflow_rl._plan_reward")
@patch("factory.games.runtime.workflow_rl._score")
@patch("factory.games.runtime.workflow_rl._load_gt")
@patch("factory.games.runtime.workflow_rl._collect_findings")
@patch("factory.games.runtime.workflow_rl._get_invoker")
def test_process_workflow_rl_emits_compact_lifecycle(
    mock_get_invoker,
    mock_collect_findings,
    mock_load_gt,
    mock_score,
    mock_plan_reward,
    mock_plan_learning,
    mock_emit,
):
    mock_get_invoker.return_value = lambda *a, **kw: {}
    mock_collect_findings.return_value = [{"agent_id": "alpha"}, {"agent_id": "beta"}]
    mock_load_gt.return_value = [{"id": "gt-1"}]
    mock_score.return_value = {
        "precision": 0.5, "recall": 1.0, "f1": 0.67,
        "true_positives": 1, "false_positives_count": 1, "false_negatives": 0,
    }
    mock_plan_reward.return_value = {"eligible": True, "amount": 67.0, "status": "pending_event"}
    mock_plan_learning.return_value = {"stored": False, "status": "pending_event"}

    report = process_workflow_rl(
        graph_id="dast-idor", run_id="run-42", vuln_class="IDOR",
        workflow_type="dast", target_app="webgoat", session_id="session-42",
    )

    assert report["scoring"]["f1"] == 0.67
    event_names = [call.args[0] for call in mock_emit.call_args_list]
    # rl.gt.edges.written is GONE post-y9tq (Neo4j edge writer deleted).
    assert event_names == [
        "rl.started", "rl.findings.collected", "rl.scored",
        "rl.reward.processed", "rl.memory.processed", "rl.completed",
    ]
    assert "rl.gt.edges.written" not in event_names
    scored_payload = mock_emit.call_args_list[2].args[1]
    assert scored_payload["workflow_run_id"] == "run-42"
    assert scored_payload["session_id"] == "session-42"
    assert scored_payload["f1"] == 0.67
    reward_payload = mock_emit.call_args_list[3].args[1]
    assert reward_payload["outcome"] == "queued"
    assert reward_payload["minted"] is True


@patch("factory.games.runtime.workflow_rl.event_emitter.emit")
@patch("factory.games.runtime.workflow_rl._plan_learning")
@patch("factory.games.runtime.workflow_rl._plan_reward")
@patch("factory.games.runtime.workflow_rl._score")
@patch("factory.games.runtime.workflow_rl._load_gt")
@patch("factory.games.runtime.workflow_rl._collect_findings")
@patch("factory.games.runtime.workflow_rl._get_invoker")
def test_process_workflow_rl_can_skip_lifecycle_emission(
    mock_get_invoker,
    mock_collect_findings,
    mock_load_gt,
    mock_score,
    mock_plan_reward,
    mock_plan_learning,
    mock_emit,
):
    mock_get_invoker.return_value = lambda *a, **kw: {}
    mock_collect_findings.return_value = []
    mock_load_gt.return_value = []
    mock_score.return_value = {"f1": 0}
    mock_plan_reward.return_value = {"eligible": False, "reason": "zero F1", "status": "no_reward"}
    mock_plan_learning.return_value = {"stored": False, "status": "pending_event"}

    process_workflow_rl(
        graph_id="dast-idor", run_id="run-42",
        workflow_type="dast", emit_lifecycle=False,
    )

    mock_emit.assert_not_called()


def test_persist_failure_does_not_break_pipeline(monkeypatch) -> None:
    """Best-effort: a raising persist invoker must not propagate."""
    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "graph_graph_query":
            return {"raw": []}
        if tool_name == "evals_evals_score_gt":
            return ToolResult(data={"f1": 0.5, "precision": 0.5, "recall": 0.5,
                                    "true_positives": 1, "false_positives_count": 1,
                                    "false_negatives": 1})
        if tool_name == "evals_evals_persist_score":
            raise RuntimeError("storage offline")
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   lambda app: [{"cwe": "CWE-89", "artifact": {"method": "GET", "path": "/x"}}])

    # Must not raise — persistence is observability, not control flow.
    result = process_workflow_rl(
        graph_id="dast-idor", run_id="run-z",
        workflow_type="dast", target_app="App",
    )
    assert result["scoring"]["f1"] == 0.5


def test_persist_uses_resolved_workflow_type_when_auto(monkeypatch) -> None:
    """workflow_type='auto' resolves to neutral 'workflow' label (no sniffing).
    match_on is rubric-sourced: when caller passes match_on, _score forwards it;
    when absent, scorer uses its own default (no match_on kwarg sent)."""
    persist_kwargs: dict = {}

    def fake_invoker(tool_name: str, **kwargs):
        if tool_name == "graph_graph_query":
            return {"raw": []}
        if tool_name == "evals_evals_score_gt":
            # With explicit match_on=["cwe","file"] passed via caller context
            assert kwargs.get("match_on") == ["cwe", "file"]
            return ToolResult(data={"f1": 0.4, "precision": 0.4, "recall": 0.4,
                                    "true_positives": 1, "false_positives_count": 0,
                                    "false_negatives": 1})
        if tool_name == "evals_evals_persist_score":
            persist_kwargs.update(kwargs)
            return {"persisted": True}
        raise AssertionError(f"unexpected tool: {tool_name}")

    _patch_invoker(monkeypatch, fake_invoker,
                   lambda app: [{"cwe": "CWE-89", "file": "db.py"}])

    process_workflow_rl(
        graph_id="rt-sast-scan", run_id="run-x",
        workflow_type="auto", target_app="App",
        match_on=["cwe", "file"],
    )

    # 'auto' resolves to neutral 'workflow', not sniffed 'sast'
    assert persist_kwargs["workflow_type"] == "workflow"
    assert persist_kwargs["workflow_type"] != "auto"
