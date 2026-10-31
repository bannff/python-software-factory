"""Tests for generic_score_dispatch — policy-driven domain-agnostic scoring.

bd:python-factory-v7imt.2 (corrected contract). Validates:
  1. Policy loading — dedicated-handler types (graph/swarm/chat) are NOT in policy
  2. Genuinely uncovered types (code_review.completed) DO match and route
  3. Opt-in default (unmatched = skip)
  4. generic_score_dispatch routes to learning_compute_reward with correct kwargs
  5. domain_class/source_tag → recall-tag alignment
  6. evaluator field removed (ScoringPolicyEntry has no evaluator attr)
  7. output_summary/input_summary forwarded to learning_compute_reward
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
import yaml

from factory.events.runtime.generic_score_dispatch import (
    ScoringPolicyEntry,
    handle_generic_score_dispatch,
    load_scoring_policy,
    match_policy,
)
from factory.events.runtime.models import Event
from factory.memory.mcp.contracts.base import MemoryData
from factory.memory.mcp.contracts.operational import MemoryStoreOutput
from factory.mcp_utils.interface import ToolResult


def _stored_memory(memory_id: str = "mem-001") -> ToolResult[MemoryStoreOutput]:
    return ToolResult(data=MemoryStoreOutput(stored=True, memory=MemoryData(
        id=memory_id, user_id="kiro-agent", content="fact", memory_type="long_term",
        category="fact", metadata={}, relevance_score=1.0, created_at="2026-01-01T00:00:00Z")))


# ---------- fixtures ----------

def _make_event(event_type: str = "code_review.completed", **payload_overrides: Any) -> Event:
    base = {
        "run_id": "run-test-001",
        "workflow_id": "wf-test",
        "workflow_type": "auto",
        "target_app": "test-app",
    }
    base.update(payload_overrides)
    return Event(
        id="evt-001",
        type=event_type,
        payload=base,
        source="test",
        timestamp=datetime.now(timezone.utc),
    )


def _mock_invoker_with_reward(source_id: str = "llm-judge", score: float = 0.85):
    """Mock invoker: learning_compute_reward returns a signal; events_publish is no-op."""
    def _invoker(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [],
                "source_id": source_id,
                "scalar": score,
                "verdict": "rewarded",
                "reward_value": score * 100,
                "wallet_id": "wallet-kiro-agent",
                "raw": {"scoring": {"f1": score, "precision": 0.9, "recall": 0.8}},
                "scoring": {"f1": score, "precision": 0.9, "recall": 0.8},
                "provenance": {"judge": "test"},
            }).model_dump(mode="json")
        if tool_name == "events_publish":
            return {"event_id": "e-mock", "status": "published"}
        if tool_name == "events_query_events":
            return {"events": []}  # not deduped
        return {}
    return _invoker


def _mock_invoker_abstain():
    """Mock invoker: all sources abstain (no source_id)."""
    def _invoker(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [], "source_id": "", "scalar": 0.0,
                "verdict": "no_reward", "reward_value": 0.0,
                "wallet_id": "wallet-kiro-agent", "provenance": {},
                "raw": {}, "scoring": {},
            }).model_dump(mode="json")
        if tool_name == "events_query_events":
            return {"events": []}
        return {}
    return _invoker


# ---------- Policy loading ----------

class TestLoadScoringPolicy:
    def test_loads_default_policy(self):
        policies = load_scoring_policy()
        assert len(policies) > 0
        # code_review.completed should be present and enabled
        cr_entry = next((p for p in policies if p.pattern == "code_review.completed"), None)
        assert cr_entry is not None
        assert cr_entry.enabled is True
        assert cr_entry.source_tag == "code-review"

    def test_dedicated_handler_types_NOT_in_policy(self):
        """graph.completed and swarm.completed are owned by rewards_dispatch.
        They must NOT appear in the scoring policy (would cause double-reward)."""
        policies = load_scoring_policy()
        patterns = [p.pattern for p in policies]
        assert "graph.completed" not in patterns, "graph.completed owned by rewards_dispatch"
        assert "swarm.completed" not in patterns, "swarm.completed owned by rewards_dispatch"

    def test_chat_types_NOT_in_policy(self):
        """chat.turn.completed and chat.feedback are owned by dedicated dispatchers."""
        policies = load_scoring_policy()
        patterns = [p.pattern for p in policies]
        assert "chat.turn.completed" not in patterns
        assert "chat.feedback" not in patterns

    def test_missing_file_returns_empty(self):
        policies = load_scoring_policy(Path("/nonexistent/path.yaml"))
        assert policies == []

    def test_custom_policy_file(self, tmp_path: Path):
        policy_file = tmp_path / "policy.yaml"
        policy_file.write_text(yaml.dump({
            "policies": [
                {"pattern": "custom.done", "source_tag": "my-domain", "enabled": True},
            ]
        }))
        policies = load_scoring_policy(policy_file)
        assert len(policies) == 1
        assert policies[0].pattern == "custom.done"
        assert policies[0].source_tag == "my-domain"

    def test_evaluator_field_removed_from_dataclass(self):
        """Meta-architect ruling: evaluator field is inert debt and was removed."""
        assert not hasattr(ScoringPolicyEntry(pattern="x"), "evaluator")


# ---------- Policy matching ----------

class TestMatchPolicy:
    def test_exact_match_uncovered_type(self):
        policies = [ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review")]
        result = match_policy("code_review.completed", policies)
        assert result is not None
        assert result.source_tag == "code-review"

    def test_wildcard_match(self):
        policies = [ScoringPolicyEntry(pattern="*.completed", source_tag="generic")]
        result = match_policy("custom.completed", policies)
        assert result is not None
        assert result.source_tag == "generic"

    def test_no_match_returns_none(self):
        policies = [ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review")]
        result = match_policy("memory.learning_stored", policies)
        assert result is None

    def test_disabled_entry_skipped(self):
        policies = [ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review", enabled=False)]
        result = match_policy("code_review.completed", policies)
        assert result is None

    def test_first_match_wins(self):
        policies = [
            ScoringPolicyEntry(pattern="code_review.completed", source_tag="specific"),
            ScoringPolicyEntry(pattern="*.completed", source_tag="generic"),
        ]
        result = match_policy("code_review.completed", policies)
        assert result is not None
        assert result.source_tag == "specific"

    def test_graph_completed_NOT_matched_by_default_policy(self):
        """graph.completed is owned by rewards_dispatch; the default policy
        must NOT have an entry that matches it (wildcard or exact)."""
        policies = load_scoring_policy()
        # Even if a *.completed wildcard existed, graph.completed must be explicitly excluded.
        # With the corrected policy (only code_review.completed), this should NOT match.
        result = match_policy("graph.completed", policies)
        # code_review.completed != graph.completed, so None is correct.
        assert result is None, "graph.completed must not match default policy"

    def test_swarm_completed_NOT_matched_by_default_policy(self):
        """swarm.completed is owned by rewards_dispatch; must not match."""
        policies = load_scoring_policy()
        result = match_policy("swarm.completed", policies)
        assert result is None, "swarm.completed must not match default policy"

    def test_unmatched_noise_events(self):
        """Telemetry noise events must NOT match the default policy."""
        policies = load_scoring_policy()
        noise_types = [
            "memory.learning_stored",
            "convergence.checked",
            "wallet.rewarded",
            "metrics.recorded",
            "eval.completed",
        ]
        for noise in noise_types:
            assert match_policy(noise, policies) is None, f"{noise} should not match"


# ---------- Handler dispatch ----------

class TestHandleGenericScoreDispatch:
    def test_uncovered_type_scores_and_emits_reward(self):
        """A genuinely uncovered type in the policy (code_review.completed)
        routes through learning_compute_reward and emits reward.computed."""
        event = _make_event("code_review.completed")
        invoker = _mock_invoker_with_reward(score=0.85)
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, mock_invoker)

        assert "skipped" not in result or result.get("skipped") is not True
        assert result["policy_pattern"] == "code_review.completed"
        assert result["domain_class"] == "code-review"
        # Verify learning_compute_reward was called with domain_class
        calls = [c for c in mock_invoker.call_args_list if c[0][0] == "learning_compute_reward"]
        assert len(calls) == 1
        assert calls[0][1]["domain_class"] == "code-review"

    def test_unmatched_event_skipped(self):
        event = _make_event("memory.learning_stored")
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "no policy match" in result["reason"]
        invoker.assert_not_called()

    def test_no_run_id_skipped(self):
        event = _make_event("code_review.completed", run_id="")
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "no run_id" in result["reason"]

    def test_abstained_sources_skipped(self):
        event = _make_event("code_review.completed")
        invoker = _mock_invoker_abstain()
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, mock_invoker)

        assert result["skipped"] is True
        assert "abstained" in result["reason"]

    def test_source_tag_becomes_domain_class_for_recall(self):
        """source_tag must flow to domain_class so memory stores
        a '{source_tag}-learnings' tag that LearningRecallPlugin can recall."""
        event = _make_event("code_review.completed")
        invoker = _mock_invoker_with_reward()
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, mock_invoker)

        assert result["domain_class"] == "code-review"
        assert event.payload["domain_class"] == "code-review"

    def test_output_summary_forwarded_to_compute(self):
        """output_summary in event payload must be forwarded to learning_compute_reward
        so llm-judge self-gating can fire (requires >= 40 chars)."""
        rich_summary = "Reviewed 3 files, found 2 issues with input validation in user profile endpoint"
        event = _make_event("code_review.completed", output_summary=rich_summary)
        invoker = _mock_invoker_with_reward()
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            handle_generic_score_dispatch(event, mock_invoker)

        calls = [c for c in mock_invoker.call_args_list if c[0][0] == "learning_compute_reward"]
        assert calls[0][1]["output_summary"] == rich_summary

    def test_input_summary_forwarded_to_compute(self):
        """input_summary forwarded when present."""
        event = _make_event("code_review.completed", input_summary="Review the auth module")
        invoker = _mock_invoker_with_reward()
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            handle_generic_score_dispatch(event, mock_invoker)

        calls = [c for c in mock_invoker.call_args_list if c[0][0] == "learning_compute_reward"]
        assert calls[0][1]["input_summary"] == "Review the auth module"

    def test_no_evaluator_kwarg_passed(self):
        """Evaluator field was removed per meta-architect ruling. No evaluator kwarg
        should ever be passed to learning_compute_reward."""
        event = _make_event("code_review.completed")
        invoker = _mock_invoker_with_reward()
        mock_invoker = MagicMock(side_effect=invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            handle_generic_score_dispatch(event, mock_invoker)

        calls = [c for c in mock_invoker.call_args_list if c[0][0] == "learning_compute_reward"]
        assert "evaluator" not in calls[0][1], "evaluator must not be passed to learning_compute_reward"

    def test_compute_exception_returns_skipped(self):
        event = _make_event("code_review.completed")

        def _exploding_invoker(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "learning_compute_reward":
                raise RuntimeError("boom")
            return {}

        mock_invoker = MagicMock(side_effect=_exploding_invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="code_review.completed", source_tag="code-review"),
            ]
            result = handle_generic_score_dispatch(event, mock_invoker)

        assert result["skipped"] is True
        assert result.get("error") == "reward_computation_failed"


# ---------- Recall-tag alignment integration ----------

class TestRecallTagAlignment:
    """Verify the source_tag → memory tag → recall alignment holds."""

    def test_memory_handler_tags_match_recall_scheme(self):
        """The memory handler uses f'{domain}-learnings' as tag. With
        domain_class='code-review', this produces 'code-review-learnings' which
        matches an agent with agent_id='code-review' querying via LearningRecallPlugin."""
        from factory.events.runtime.learning_handlers.memory import handle_memory_learning

        # Simulate a reward.computed event with domain_class from the policy
        reward_event = Event(
            id="evt-r1",
            type="reward.computed",
            payload={
                "run_id": "run-test-002",
                "workflow_run_id": "run-test-002",
                "workflow_id": "wf-test",
                "workflow_type": "auto",
                "domain_class": "code-review",  # <-- set by generic_score_dispatch
                "target_app": "test-app",
                "score": 0.85,
                "precision": 0.9,
                "recall": 0.8,
            },
            source="test",
            timestamp=datetime.now(timezone.utc),
        )
        stored_memory: dict[str, Any] = {}

        def _invoker(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "events_query_events":
                return {"events": []}  # not deduped
            if tool_name == "memory_memory_store":
                stored_memory.update(kwargs)
                return _stored_memory()
            if tool_name == "events_publish":
                return {"event_id": "e-mock"}
            return {}

        result = handle_memory_learning(reward_event, _invoker)
        assert result.get("status") == "stored"

        # Verify the stored tags include the recall-matchable tag
        tags = stored_memory.get("metadata", {}).get("tags", [])
        assert "code-review-learnings" in tags, f"Expected 'code-review-learnings' in {tags}"
        assert "auto-learnings" in tags, f"Expected 'auto-learnings' in {tags}"
