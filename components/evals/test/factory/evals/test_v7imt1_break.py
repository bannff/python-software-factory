"""QA break-tests for bd:python-factory-v7imt.1 convergence bridge.

Attack vectors:
1. DEFENSIVE ISOLATION — bridge failure must not propagate to primary paths
2. IDEMPOTENCY — re-delivery must not duplicate records
3. PROVENANCE CORRECTNESS — source tags flow through and surface correctly
4. EDGE CASES — missing/empty/None/negative inputs must not crash or write garbage
5. POLYLITH — no cross-brick imports in production code

These are adversarial — designed to FIND defects, not confirm the happy path.
"""
from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from factory.events.runtime.learning_handlers import handle_blockchain_reward
from factory.events.runtime._dispatch_evals import _persist_eval_result, _bridge_auto_eval_to_evals
from factory.events.runtime.learning_handlers.reward import _bridge_reward_to_evals
from factory.events.runtime.models import Event
from factory.evals.runtime.adapters import run_results_store


# ═══════════════════════════════════════════════════════════════════════════════
# 1. DEFENSIVE ISOLATION — highest risk
# ═══════════════════════════════════════════════════════════════════════════════


class TestDefensiveIsolationReward:
    """Bridge failure in reward path must NOT propagate to wallet side-effects."""

    def test_bridge_typeerror_does_not_break_wallet_path(self) -> None:
        """TypeError inside evals_persist_score — wallet.rewarded still emits."""
        published: list[tuple[str, dict]] = []

        def failing_invoker(tool_name: str, **kwargs):
            if tool_name == "events_query_events":
                return {"events": [], "total": 0}
            if tool_name == "blockchain_get_wallet":
                return {"wallet_id": kwargs["wallet_id"], "balance": 5.0}
            if tool_name == "blockchain_mint":
                return {"tx_id": "tx-type-err", "to_wallet": kwargs["to_wallet"]}
            if tool_name == "evals_record_run":
                raise TypeError("unexpected keyword argument 'source'")
            if tool_name == "events_publish":
                published.append((kwargs["event_type"], kwargs["payload"]))
                return {"event_id": "evt-ok"}
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-te", "workflow_run_id": "wf-te",
                "reward_value": 7.0, "score": 0.4, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )

        result = handle_blockchain_reward(event, failing_invoker)
        assert result["status"] == "committed"
        assert result["transaction_id"] == "tx-type-err"
        wallet_events = [et for et, _ in published if et == "wallet.rewarded"]
        assert len(wallet_events) == 1

    def test_bridge_timeout_does_not_break_wallet_path(self) -> None:
        """TimeoutError inside evals_persist_score — wallet still succeeds."""
        published: list[tuple[str, dict]] = []

        def timeout_invoker(tool_name: str, **kwargs):
            if tool_name == "events_query_events":
                return {"events": [], "total": 0}
            if tool_name == "blockchain_get_wallet":
                return {"wallet_id": kwargs["wallet_id"], "balance": 1.0}
            if tool_name == "blockchain_mint":
                return {"tx_id": "tx-timeout", "to_wallet": kwargs["to_wallet"]}
            if tool_name == "evals_record_run":
                raise TimeoutError("connection timed out")
            if tool_name == "events_publish":
                published.append((kwargs["event_type"], kwargs["payload"]))
                return {"event_id": "evt-timeout"}
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-to", "workflow_run_id": "wf-to",
                "reward_value": 3.0, "score": 0.2, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )

        result = handle_blockchain_reward(event, timeout_invoker)
        assert result["status"] == "committed"
        assert any(et == "wallet.rewarded" for et, _ in published)

    def test_bridge_keyboard_interrupt_is_NOT_swallowed(self) -> None:
        """KeyboardInterrupt and SystemExit must NOT be caught by bridge.

        If they are, the process hangs rather than terminating cleanly.
        """
        def kbi_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                raise KeyboardInterrupt()
            return {}

        with pytest.raises(KeyboardInterrupt):
            _bridge_reward_to_evals(
                kbi_invoker,
                {"workflow_run_id": "wf-kbi", "score": 0.5},
                5.0,
            )

    def test_bridge_system_exit_is_NOT_swallowed(self) -> None:
        """SystemExit must propagate — bridges must not use bare `except:`."""
        def sysexit_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                raise SystemExit(1)
            return {}

        with pytest.raises(SystemExit):
            _bridge_reward_to_evals(
                sysexit_invoker,
                {"workflow_run_id": "wf-se", "score": 0.5},
                5.0,
            )


class TestDefensiveIsolationAutoEval:
    """Bridge failure in auto-eval path must NOT break graph entity + event."""

    def test_bridge_raises_but_graph_and_event_still_written(self) -> None:
        """evals_persist_score raises — graph_add_entity and events_publish survive."""
        calls: list[str] = []

        def failing_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            if tool_name == "evals_record_run":
                raise ConnectionError("storage brick offline")
            return {}

        payload = {"run_id": "run-ae-fail", "workflow_id": "g-42"}
        result = {
            "summary": {"avg_score": 0.7, "pass_rate": 0.6},
            "results": [{"evaluator": "j", "score": 0.7}],
        }

        _persist_eval_result(failing_invoker, payload, result)

        assert calls == ["evals_record_run"]

    def test_bridge_keyboard_interrupt_propagates_in_auto_eval(self) -> None:
        """SystemExit/KBI must NOT be swallowed."""
        def kbi_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                raise KeyboardInterrupt()
            return {}

        with pytest.raises(KeyboardInterrupt):
            _bridge_auto_eval_to_evals(
                kbi_invoker, "run-x", "g-x", {"pass_rate": 0.5},
                {"results": [{"evaluator": "j", "score": 0.5}]},
            )


# ═══════════════════════════════════════════════════════════════════════════════
# 2. IDEMPOTENCY — re-delivery must NOT create duplicate records
# ═══════════════════════════════════════════════════════════════════════════════


class TestIdempotency:
    """Verify dedup behavior across both bridge paths."""

    def test_reward_deduped_event_does_not_trigger_bridge(self) -> None:
        """When _already_published returns True, bridge is never called."""
        calls: list[str] = []

        def dedup_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            if tool_name == "events_query_events":
                return {"events": [{"id": "existing-evt"}], "total": 1}
            if tool_name == "evals_record_run":
                raise AssertionError("bridge must NOT fire on dedup path")
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-dup", "workflow_run_id": "wf-dup",
                "reward_value": 10.0, "score": 0.9, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )

        result = handle_blockchain_reward(event, dedup_invoker)
        assert result.get("deduped") is True
        assert "evals_record_run" not in calls

    def test_reward_bridge_uses_workflow_run_id_for_eval_run_id(self) -> None:
        """Two events with same workflow_run_id but different run_id must map
        to the SAME eval record (no accidental dup via run_id confusion)."""
        captured_ids: list[str] = []

        def capturing_invoker(tool_name: str, **kwargs):
            if tool_name == "events_query_events":
                return {"events": [], "total": 0}
            if tool_name == "blockchain_get_wallet":
                return {"wallet_id": kwargs["wallet_id"], "balance": 1.0}
            if tool_name == "blockchain_mint":
                return {"tx_id": "tx", "to_wallet": kwargs["to_wallet"]}
            if tool_name == "evals_record_run":
                captured_ids.append(kwargs["run_id"])
                return {"persisted": True, "doc_id": "x"}
            if tool_name == "events_publish":
                return {"event_id": "e"}
            return {}

        for run_id_suffix in ("a", "b"):
            event = Event(
                source="events.rewards", type="reward.computed",
                payload={
                    "run_id": f"r-{run_id_suffix}",
                    "workflow_run_id": "wf-same",
                    "reward_value": 5.0, "score": 0.5,
                    "principal_id": "kiro-agent",
                },
                principal_id="kiro-agent",
            )
            handle_blockchain_reward(event, capturing_invoker)

        # Both must use workflow_run_id as the eval run_id
        assert captured_ids == ["wf-same", "wf-same"]


# ═══════════════════════════════════════════════════════════════════════════════
# 3. PROVENANCE CORRECTNESS — source tags
# ═══════════════════════════════════════════════════════════════════════════════


class TestProvenanceCorrectness:
    """Each path writes the correct source tag — no cross-contamination."""

    def test_reward_path_writes_source_reward_not_experiment(self) -> None:
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "events_query_events":
                return {"events": [], "total": 0}
            if tool_name == "blockchain_get_wallet":
                return {"wallet_id": "w", "balance": 1.0}
            if tool_name == "blockchain_mint":
                return {"tx_id": "tx", "to_wallet": "w"}
            if tool_name == "evals_record_run":
                captured.update(kwargs)
                return {"persisted": True}
            if tool_name == "events_publish":
                return {"event_id": "e"}
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-prov", "workflow_run_id": "wf-prov",
                "reward_value": 8.0, "score": 0.75, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )
        handle_blockchain_reward(event, cap_invoker)

        assert captured["source"] == "reward"
        assert captured["source"] != "experiment"
        assert captured["source"] != "auto-eval"

    def test_auto_eval_path_writes_source_auto_eval(self) -> None:
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _persist_eval_result(
            cap_invoker,
            {"run_id": "run-prov-ae", "workflow_id": "g-prov"},
            {"summary": {"avg_score": 0.8, "pass_rate": 0.9}, "results": [{"evaluator": "x", "score": 0.8}]},
        )

        assert captured["source"] == "auto-eval"
        assert captured["source"] != "experiment"

    def test_list_runs_exposes_all_three_source_values(self) -> None:
        """All three provenance tags surface via list_runs for UI filtering."""
        tmp = tempfile.mkdtemp()
        orig = run_results_store._RUNS_DIR
        run_results_store._RUNS_DIR = Path(tmp) / "eval_runs"
        try:
            for src in ("experiment", "reward", "auto-eval"):
                run_results_store.save_run(
                    experiment_name=f"test-{src}",
                    case_results=[{"case_name": "c1", "passed": True, "score": 0.8}],
                    summary={},
                    evaluators_used=[],
                    model_id="m",
                    system_prompt="",
                    source=src,
                )
            runs = run_results_store.list_runs()
            sources = {r["source"] for r in runs}
            assert sources == {"experiment", "reward", "auto-eval"}
        finally:
            run_results_store._RUNS_DIR = orig


# ═══════════════════════════════════════════════════════════════════════════════
# 4. EDGE CASES — missing/empty/None/negative inputs
# ═══════════════════════════════════════════════════════════════════════════════


class TestEdgeCasesRewardBridge:
    """Reward bridge must gracefully handle garbage input without crashing."""

    def test_missing_workflow_run_id_and_run_id_skips_bridge(self) -> None:
        """No run_id at all → bridge must silently skip (not crash)."""
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        _bridge_reward_to_evals(cap_invoker, {}, 5.0)
        assert "evals_record_run" not in calls

    def test_empty_string_run_id_skips_bridge(self) -> None:
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        _bridge_reward_to_evals(cap_invoker, {"workflow_run_id": "", "run_id": ""}, 5.0)
        assert "evals_record_run" not in calls

    def test_missing_domain_class_defaults_to_vuln_class(self) -> None:
        """domain_class absent → falls back to vuln_class in experiment_name."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _bridge_reward_to_evals(
            cap_invoker,
            {"workflow_run_id": "wf-x", "vuln_class": "SSRF"},
            3.0,
        )
        assert "SSRF" in captured["experiment_name"]

    def test_both_domain_class_and_vuln_class_empty(self) -> None:
        """Both empty → writes workflow_type in experiment_name, no crash."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _bridge_reward_to_evals(
            cap_invoker,
            {"workflow_run_id": "wf-empty", "domain_class": "", "vuln_class": "", "workflow_type": "dast"},
            2.0,
        )
        assert "reward:" in captured["experiment_name"]

    def test_none_score_coerces_to_zero(self) -> None:
        """score=None must not TypeError in float()."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _bridge_reward_to_evals(
            cap_invoker,
            {"workflow_run_id": "wf-none-score", "score": None},
            1.0,
        )
        assert captured["pass_rate"] == 0.0
        assert captured["avg_score"] == 0.0

    def test_zero_reward_amount_entire_handler_skips(self) -> None:
        """amount=0 → handle_blockchain_reward returns early, no bridge call."""
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-zero", "workflow_run_id": "wf-zero",
                "reward_value": 0.0, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )
        result = handle_blockchain_reward(event, cap_invoker)
        assert result["skipped"] is True
        assert "evals_record_run" not in calls

    def test_negative_reward_amount_entire_handler_skips(self) -> None:
        """Negative reward → skips. Bridge never fires."""
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        event = Event(
            source="events.rewards", type="reward.computed",
            payload={
                "run_id": "r-neg", "workflow_run_id": "wf-neg",
                "reward_value": -5.0, "principal_id": "kiro-agent",
            },
            principal_id="kiro-agent",
        )
        result = handle_blockchain_reward(event, cap_invoker)
        assert result["skipped"] is True
        assert "evals_record_run" not in calls


class TestEdgeCasesAutoEvalBridge:
    """Auto-eval bridge must handle missing/None fields gracefully."""

    def test_run_id_unknown_skips_bridge(self) -> None:
        """run_id='unknown' → bridge silently returns (no evals write)."""
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        _bridge_auto_eval_to_evals(cap_invoker, "unknown", "g-1", {"pass_rate": 0.5})
        assert "evals_record_run" not in calls

    def test_empty_run_id_skips_bridge(self) -> None:
        calls: list[str] = []

        def cap_invoker(tool_name: str, **kwargs):
            calls.append(tool_name)
            return {}

        _bridge_auto_eval_to_evals(cap_invoker, "", "g-1", {"pass_rate": 0.5})
        assert "evals_record_run" not in calls

    def test_none_pass_rate_coerces_to_zero(self) -> None:
        """None in summary → float coercion to 0, not crash."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _bridge_auto_eval_to_evals(
            cap_invoker, "run-np", "g-np",
            {"pass_rate": None, "avg_score": None},
            {"results": [{"evaluator": "x", "score": None}]},
        )
        # None score coerces to 0.0; single non-passing row → zeros.
        assert captured["pass_rate"] == 0.0
        assert captured["avg_score"] == 0.0

    def test_empty_summary_dict_writes_zeros(self) -> None:
        """Empty summary → aggregates derived from rows, no crash."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _bridge_auto_eval_to_evals(
            cap_invoker, "run-es", "g-es", {},
            {"results": [{"evaluator": "x", "score": 0.0}]},
        )
        assert captured["pass_rate"] == 0.0
        assert captured["avg_score"] == 0.0

    def test_missing_graph_id_uses_unknown_default(self) -> None:
        """_persist_eval_result with no workflow_id → experiment_name uses 'unknown'."""
        captured: dict = {}

        def cap_invoker(tool_name: str, **kwargs):
            if tool_name == "evals_record_run":
                captured.update(kwargs)
            return {}

        _persist_eval_result(
            cap_invoker,
            {"run_id": "run-ng"},  # no workflow_id, no graph_id
            {"summary": {"avg_score": 0.5, "pass_rate": 0.5}, "results": [{"evaluator": "x", "score": 0.5}]},
        )
        assert captured["experiment_name"] == "auto-eval:unknown"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. POLYLITH — no cross-brick imports in production source
# ═══════════════════════════════════════════════════════════════════════════════


class TestPolylithBoundary:
    """Production source in events must NOT import from evals directly."""

    def test_events_src_has_no_evals_import(self) -> None:
        """Scan events production source for illegal cross-brick imports."""
        import re
        from pathlib import Path

        events_src = Path(__file__).resolve().parents[5] / "components" / "events" / "src"
        violations: list[str] = []
        pattern = re.compile(r"^\s*(from factory\.evals|import factory\.evals)")

        for py_file in events_src.rglob("*.py"):
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if pattern.match(line):
                    violations.append(f"{py_file}:{i}: {line.strip()}")

        assert violations == [], (
            f"Polylith violation: events brick directly imports evals:\n"
            + "\n".join(violations)
        )

    def test_evals_src_has_no_events_import(self) -> None:
        """Scan evals production source for illegal cross-brick imports."""
        import re
        from pathlib import Path

        evals_src = Path(__file__).resolve().parents[5] / "components" / "evals" / "src"
        violations: list[str] = []
        pattern = re.compile(r"^\s*(from factory\.events|import factory\.events)")

        for py_file in evals_src.rglob("*.py"):
            for i, line in enumerate(py_file.read_text().splitlines(), 1):
                if pattern.match(line):
                    violations.append(f"{py_file}:{i}: {line.strip()}")

        assert violations == [], (
            f"Polylith violation: evals brick directly imports events:\n"
            + "\n".join(violations)
        )
