"""Adversarial break-tests for generic_score_dispatch (bd:python-factory-v7imt.2).

QA contract: hunt edge cases and failure modes the implementer's happy-path
tests miss. Every test names one specific contract that must hold.

Attack vectors:
1. Opt-in discipline — unmatched events MUST be skipped (no eval row, no scoring call)
2. Disabled policy — chat.turn.completed MUST NOT double-score (dedicated handler owns it)
3. Abstained sources — empty source_id → skipped, no spam row
4. Missing run_id — skipped gracefully
5. Malformed/missing scoring_policy.yaml — load returns [] and handler no-ops
6. Polylith boundary — no cross-brick production imports (events → evals/learning/memory only via invoker)
7. Wildcard abuse — greedy wildcard must not match internal noise events
8. Concurrency — handler must not mutate shared state unsafely
9. Defensive isolation — invoker explosions must not crash dispatch loop
10. Policy priority — first-match wins, lower entries shadowed

Timeout: all tests run with pytest-timeout to prevent hangs from wedging the agent.
"""

from __future__ import annotations

import importlib
import inspect
import os
import sys
import tempfile
import textwrap
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch, call

import pytest
import yaml

from factory.events.runtime.generic_score_dispatch import (
    ScoringPolicyEntry,
    handle_generic_score_dispatch,
    load_scoring_policy,
    match_policy,
)
from factory.events.runtime.models import Event
from factory.mcp_utils.interface import ToolResult


# ---------- Fixtures ----------

def _make_event(event_type: str = "graph.completed", **payload_overrides: Any) -> Event:
    base = {
        "run_id": "run-break-v7imt2-001",
        "workflow_id": "wf-break",
        "workflow_type": "auto",
        "target_app": "qa-break-app",
    }
    base.update(payload_overrides)
    return Event(type=event_type, source="qa-break-v7imt2", payload=base)


def _reward_invoker(source_id: str = "llm-judge", score: float = 0.75):
    """Invoker that returns a scoring signal."""
    def _invoker(tool_name: str, **kwargs: Any) -> Any:
        if tool_name == "learning_compute_reward":
            return ToolResult(ok=True, data={
                "signals": [],
                "source_id": source_id,
                "scalar": score,
                "verdict": "rewarded",
                "reward_value": score * 100,
                "wallet_id": "wallet-kiro-agent",
                "raw": {"scoring": {"f1": score, "precision": 0.8, "recall": 0.7}},
                "scoring": {"f1": score, "precision": 0.8, "recall": 0.7},
                "provenance": {"judge": "qa-break"},
            }).model_dump(mode="json")
        if tool_name == "events_publish":
            return {"event_id": "e-qa-break", "status": "published"}
        if tool_name == "events_query_events":
            return {"events": []}  # not deduped
        return {}
    return _invoker


def _abstain_invoker():
    """All reward sources abstain."""
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


# ===========================================================================
# 1. OPT-IN DISCIPLINE — unmatched events MUST be skipped
# ===========================================================================

class TestOptInDiscipline:
    """Events not in the scoring policy must never trigger scoring."""

    @pytest.mark.timeout(10)
    def test_random_completed_is_skipped(self):
        """A random *.completed event with no policy entry → skipped."""
        event = _make_event("random.completed")
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
                ScoringPolicyEntry(pattern="swarm.completed", source_tag="swarm"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "no policy match" in result["reason"]
        # Critical: learning_compute_reward MUST NOT have been called
        invoker.assert_not_called()

    @pytest.mark.timeout(10)
    def test_internal_noise_events_never_scored(self):
        """Internal bus events (memory, convergence, wallet, metrics, eval) must never match."""
        noise_events = [
            "memory.learning_stored",
            "convergence.checked",
            "wallet.rewarded",
            "metrics.recorded",
            "eval.completed",
            "blockchain.reward_minted",
            "notification.sent",
            "telemetry.recorded",
        ]
        # Load the REAL policy (not mocked)
        policies = load_scoring_policy()
        for noise_type in noise_events:
            matched = match_policy(noise_type, policies)
            assert matched is None, f"SECURITY: internal event '{noise_type}' matched policy '{matched}'"

    @pytest.mark.timeout(10)
    def test_wildcard_does_not_match_noise_without_completed_suffix(self):
        """The *.completed subscription pattern means ONLY events ending in .completed
        reach the handler (enforced by subscription), but the policy itself must also
        not have greedy wildcards matching non-completed noise."""
        policies = [ScoringPolicyEntry(pattern="*.completed", source_tag="generic")]
        # These should NOT end up in the handler (subscription blocks them),
        # but verify the policy alone doesn't match them either
        non_completed = ["graph.started", "swarm.failed", "chat.aborted"]
        for ev_type in non_completed:
            assert match_policy(ev_type, policies) is None


# ===========================================================================
# 2. DISABLED POLICY — chat.turn.completed MUST NOT double-score
# ===========================================================================

class TestDisabledPolicyNoDoubleScore:
    """Disabled entries must not route through the generic handler."""

    @pytest.mark.timeout(10)
    def test_disabled_chat_turn_completed_skipped(self):
        """chat.turn.completed is disabled in default policy → must skip."""
        event = _make_event("chat.turn.completed")
        invoker = MagicMock()

        # Load real policy (has chat.turn.completed disabled)
        result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        # learning_compute_reward must NOT be called — dedicated handler owns this
        calls = [c for c in invoker.call_args_list if "learning_compute_reward" in str(c)]
        assert len(calls) == 0, "DOUBLE-SCORE: disabled entry still triggered scoring"

    @pytest.mark.timeout(10)
    def test_disabled_chat_feedback_skipped(self):
        """chat.feedback is disabled in default policy → must skip."""
        event = _make_event("chat.feedback")
        invoker = MagicMock()

        result = handle_generic_score_dispatch(event, invoker)
        assert result["skipped"] is True

    @pytest.mark.timeout(10)
    def test_dedicated_handler_types_absent_from_policy(self):
        """graph.completed, swarm.completed, chat.* are owned by dedicated handlers
        and must NOT appear in the scoring policy at all (would cause double-reward)."""
        policies = load_scoring_policy()
        patterns = [p.pattern for p in policies]
        dedicated_owned = ["graph.completed", "swarm.completed", "chat.turn.completed", "chat.feedback"]
        for owned_type in dedicated_owned:
            assert owned_type not in patterns, (
                f"DOUBLE-REWARD: '{owned_type}' in scoring_policy but owned by a dedicated handler"
            )


# ===========================================================================
# 3. ABSTAINED SOURCES — no spam eval row
# ===========================================================================

class TestAbstainedSources:
    """When all reward sources abstain, no eval row or reward event."""

    @pytest.mark.timeout(10)
    def test_empty_source_id_means_skipped(self):
        """Empty source_id from compute → skipped, no reward.computed emitted."""
        event = _make_event("graph.completed")
        invoker = MagicMock(side_effect=_abstain_invoker())

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "abstained" in result["reason"]
        # events_publish must NOT have been called (no reward.computed emission)
        publish_calls = [c for c in invoker.call_args_list if c[0][0] == "events_publish"]
        assert len(publish_calls) == 0, "SPAM: reward.computed emitted despite abstention"

    @pytest.mark.timeout(10)
    def test_none_source_id_means_skipped(self):
        """None source_id (not just empty string) → skipped."""
        event = _make_event("graph.completed")

        def _none_source_invoker(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "learning_compute_reward":
                return {"source_id": None, "raw": {}}
            if tool_name == "events_query_events":
                return {"events": []}
            return {}

        invoker = MagicMock(side_effect=_none_source_invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True


# ===========================================================================
# 4. MISSING RUN_ID — skipped gracefully
# ===========================================================================

class TestMissingRunId:
    """Events without run_id must be skipped without calling compute."""

    @pytest.mark.timeout(10)
    def test_empty_string_run_id_skipped(self):
        event = _make_event("graph.completed", run_id="")
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "no run_id" in result["reason"]
        invoker.assert_not_called()

    @pytest.mark.timeout(10)
    def test_missing_run_id_key_skipped(self):
        """Payload with no run_id key at all → skipped."""
        event = Event(
            type="graph.completed",
            source="qa-break",
            payload={"workflow_id": "wf-1", "workflow_type": "auto"},  # No run_id!
        )
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert "no run_id" in result["reason"]


# ===========================================================================
# 5. MALFORMED/MISSING scoring_policy.yaml — defensive isolation
# ===========================================================================

class TestMalformedPolicy:
    """Broken YAML must not crash the dispatch loop."""

    @pytest.mark.timeout(10)
    def test_invalid_yaml_returns_empty_list(self, tmp_path: Path):
        """Corrupt YAML → load returns [], handler skips."""
        bad_file = tmp_path / "bad.yaml"
        bad_file.write_text("policies: [[[{invalid yaml !!!")
        policies = load_scoring_policy(bad_file)
        assert policies == []

    @pytest.mark.timeout(10)
    def test_empty_yaml_file_returns_empty_list(self, tmp_path: Path):
        """Empty file → load returns []."""
        empty_file = tmp_path / "empty.yaml"
        empty_file.write_text("")
        policies = load_scoring_policy(empty_file)
        assert policies == []

    @pytest.mark.timeout(10)
    def test_yaml_with_no_policies_key_returns_empty(self, tmp_path: Path):
        """YAML exists but missing 'policies' key → []."""
        no_key = tmp_path / "nokey.yaml"
        no_key.write_text(yaml.dump({"something_else": [1, 2, 3]}))
        policies = load_scoring_policy(no_key)
        assert policies == []

    @pytest.mark.timeout(10)
    def test_policies_with_non_dict_entries_skipped(self, tmp_path: Path):
        """Policy entries that aren't dicts → silently skipped."""
        weird = tmp_path / "weird.yaml"
        weird.write_text(yaml.dump({
            "policies": [
                "just a string",
                42,
                None,
                {"pattern": "valid.completed", "source_tag": "ok", "enabled": True},
            ]
        }))
        policies = load_scoring_policy(weird)
        assert len(policies) == 1
        assert policies[0].pattern == "valid.completed"

    @pytest.mark.timeout(10)
    def test_handler_noop_when_no_policy_loads(self):
        """When load_scoring_policy returns [], handler skips everything."""
        event = _make_event("graph.completed")
        invoker = MagicMock()

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = []
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        invoker.assert_not_called()


# ===========================================================================
# 6. POLYLITH BOUNDARY — no cross-brick production imports
# ===========================================================================

class TestPolylithBoundary:
    """Events brick must not import from evals/learning/memory bricks directly."""

    @pytest.mark.timeout(10)
    def test_no_cross_brick_imports_in_generic_score_dispatch(self):
        """generic_score_dispatch.py must not import from factory.evals, factory.learning,
        or factory.memory — those are reached only via the invoker."""
        src_path = Path(__file__).parent.parent.parent.parent.parent / "src" / "factory" / "events" / "runtime" / "generic_score_dispatch.py"
        if not src_path.exists():
            # Try alternate path resolution
            import factory.events.runtime.generic_score_dispatch as mod
            src_path = Path(inspect.getfile(mod))

        source = src_path.read_text()
        forbidden_imports = [
            "from factory.evals",
            "from factory.learning",
            "from factory.memory",
            "import factory.evals",
            "import factory.learning",
            "import factory.memory",
        ]
        for forbidden in forbidden_imports:
            assert forbidden not in source, (
                f"POLYLITH VIOLATION: {src_path.name} has '{forbidden}' — "
                f"must use invoker() for cross-brick calls"
            )

    @pytest.mark.timeout(10)
    def test_no_cross_brick_imports_in_rewards_handler(self):
        """rewards_handler.py must also not import from other bricks."""
        import factory.events.runtime.rewards_handler as mod
        src_path = Path(inspect.getfile(mod))
        source = src_path.read_text()
        forbidden = ["from factory.evals", "from factory.learning", "from factory.memory"]
        for f in forbidden:
            assert f not in source, f"POLYLITH VIOLATION: rewards_handler has '{f}'"


# ===========================================================================
# 7. DEFENSIVE ISOLATION — invoker explosions must not crash dispatch
# ===========================================================================

class TestDefensiveIsolation:
    """The handler must catch and contain invoker failures gracefully."""

    @pytest.mark.timeout(10)
    def test_invoker_raises_exception_returns_skipped(self):
        """Runtime error from learning_compute_reward → graceful skip."""
        event = _make_event("graph.completed")

        def _exploding(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "learning_compute_reward":
                raise RuntimeError("upstream brick is down")
            return {}

        invoker = MagicMock(side_effect=_exploding)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True
        assert result.get("error") == "reward_computation_failed"

    @pytest.mark.timeout(10)
    def test_invoker_returns_none_treated_as_abstain(self):
        """If compute returns None instead of dict → treat as abstained."""
        event = _make_event("graph.completed")

        def _none_invoker(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "learning_compute_reward":
                return None
            if tool_name == "events_query_events":
                return {"events": []}
            return {}

        invoker = MagicMock(side_effect=_none_invoker)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True

    @pytest.mark.timeout(10)
    def test_invoker_timeout_exception_handled(self):
        """TimeoutError → graceful skip."""
        event = _make_event("graph.completed")

        def _timeout(tool_name: str, **kwargs: Any) -> Any:
            if tool_name == "learning_compute_reward":
                raise TimeoutError("brick timed out")
            return {}

        invoker = MagicMock(side_effect=_timeout)

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="workflow"),
            ]
            result = handle_generic_score_dispatch(event, invoker)

        assert result["skipped"] is True


# ===========================================================================
# 8. POLICY PRIORITY AND SHADOWING
# ===========================================================================

class TestPolicyPriority:
    """First-match-wins semantics verified."""

    @pytest.mark.timeout(10)
    def test_first_match_wins_specific_over_wildcard(self):
        """A specific pattern before a wildcard → specific wins."""
        policies = [
            ScoringPolicyEntry(pattern="graph.completed", source_tag="specific-wf"),
            ScoringPolicyEntry(pattern="*.completed", source_tag="generic-catch-all"),
        ]
        result = match_policy("graph.completed", policies)
        assert result is not None
        assert result.source_tag == "specific-wf"

    @pytest.mark.timeout(10)
    def test_wildcard_catches_unmatched_specific(self):
        """Wildcard matches events that have no specific entry."""
        policies = [
            ScoringPolicyEntry(pattern="graph.completed", source_tag="specific-wf"),
            ScoringPolicyEntry(pattern="*.completed", source_tag="generic-catch-all"),
        ]
        result = match_policy("custom.completed", policies)
        assert result is not None
        assert result.source_tag == "generic-catch-all"

    @pytest.mark.timeout(10)
    def test_disabled_first_match_does_not_shadow_enabled_wildcard(self):
        """A disabled specific entry must not shadow an enabled wildcard below it."""
        policies = [
            ScoringPolicyEntry(pattern="graph.completed", source_tag="disabled-wf", enabled=False),
            ScoringPolicyEntry(pattern="*.completed", source_tag="catch-all", enabled=True),
        ]
        result = match_policy("graph.completed", policies)
        assert result is not None
        assert result.source_tag == "catch-all"


# ===========================================================================
# 9. SUBSCRIPTION WIRING — dispatch.py routes correctly
# ===========================================================================

class TestDispatchWiring:
    """Verify dispatch.py correctly delegates to handle_generic_score_dispatch."""

    @pytest.mark.timeout(10)
    def test_generic_score_dispatch_registered_in_dispatch_router(self):
        """dispatch.py must have a branch for tool_name == 'generic_score_dispatch'."""
        import factory.events.runtime.dispatch as dispatch_mod
        source = Path(inspect.getfile(dispatch_mod)).read_text()
        assert 'tool_name == "generic_score_dispatch"' in source
        assert "handle_generic_score_dispatch" in source

    @pytest.mark.timeout(10)
    def test_subscription_yaml_exists_and_is_valid(self):
        """auto-generic-score-dispatch.yaml must exist, be enabled, and route correctly."""
        sub_dir = Path(__file__).parent.parent.parent.parent.parent / "src" / "factory" / "events" / "subscriptions"
        # Try alternate resolution
        if not sub_dir.exists():
            import factory.events.runtime.generic_score_dispatch as mod
            sub_dir = Path(inspect.getfile(mod)).parent.parent / "subscriptions"

        yaml_path = sub_dir / "auto-generic-score-dispatch.yaml"
        assert yaml_path.exists(), f"Subscription YAML not found at {yaml_path}"

        data = yaml.safe_load(yaml_path.read_text())
        assert data["id"] == "auto-generic-score-dispatch"
        assert data["event_type"] == "*.completed"
        assert data["handler"] == "mcp:generic_score_dispatch"
        assert data["enabled"] is True


# ===========================================================================
# 10. EDGE CASES — boundary conditions
# ===========================================================================

class TestEdgeCases:
    """Misc boundary conditions."""

    @pytest.mark.timeout(10)
    def test_empty_pattern_matches_nothing(self):
        """An entry with empty pattern should not match anything."""
        policies = [ScoringPolicyEntry(pattern="", source_tag="empty")]
        # fnmatch("graph.completed", "") should be False
        result = match_policy("graph.completed", policies)
        assert result is None

    @pytest.mark.timeout(10)
    def test_event_payload_mutation_injects_domain_class(self):
        """The handler injects domain_class into event.payload for downstream."""
        event = _make_event("graph.completed")
        assert event.payload.get("domain_class") is None or event.payload.get("domain_class") == ""

        invoker = MagicMock(side_effect=_reward_invoker())

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag="injected-domain"),
            ]
            handle_generic_score_dispatch(event, invoker)

        assert event.payload["domain_class"] == "injected-domain"

    @pytest.mark.timeout(10)
    def test_payload_domain_class_not_overridden_when_source_tag_empty(self):
        """When source_tag is empty, existing payload domain_class is preserved."""
        event = _make_event("graph.completed", domain_class="existing-domain")
        invoker = MagicMock(side_effect=_reward_invoker())

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag=""),
            ]
            handle_generic_score_dispatch(event, invoker)

        assert event.payload["domain_class"] == "existing-domain"

    @pytest.mark.timeout(10)
    def test_both_source_tag_and_domain_class_missing_falls_to_agent_id(self):
        """When source_tag="" and no domain_class in payload, falls to agent_id."""
        event = _make_event("graph.completed", agent_id="my-agent")
        # Ensure no domain_class key
        event.payload.pop("domain_class", None)

        invoker = MagicMock(side_effect=_reward_invoker())

        with patch("factory.events.runtime.generic_score_dispatch.load_scoring_policy") as mock_load:
            mock_load.return_value = [
                ScoringPolicyEntry(pattern="graph.completed", source_tag=""),
            ]
            handle_generic_score_dispatch(event, invoker)

        assert event.payload["domain_class"] == "my-agent"
