"""Core tests for the learning reward-source seam: registry, gt-findings,
runtime.compute (bd python-factory-pfvo9). Per-source adapter tests
(llm-judge, user-feedback, telemetry, signed scalar) live in test_sources.py."""

from __future__ import annotations

from typing import Any

import pytest

from factory.learning.runtime.adapters.generic import GenericFallbackRewardSource
from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.mcp_utils.interface import ToolResult


class _FakeSource:
    def __init__(self, source_id: str) -> None:
        self.source_id = source_id

    def signal_or_none(self, run_ctx, invoker):  # pragma: no cover - trivial
        return None


def _games_invoker(result: Any):
    def _invoke(tool: str, **kwargs):
        assert tool == "games_process_workflow_rl"
        return result
    return _invoke


# -- registry ---------------------------------------------------------------

def test_registry_builtins_win_over_overlay() -> None:
    reg = RewardSourceRegistry()
    builtin = _FakeSource("gt-findings")
    reg.register_builtin(builtin)
    reg.register(_FakeSource("gt-findings"))  # pack source, same id → ignored
    sources = reg.sources()
    assert len(sources) == 1
    assert sources[0] is builtin
    assert reg.source_ids() == ["gt-findings"]


def test_generic_fallback_abstains() -> None:
    sig = GenericFallbackRewardSource().signal_or_none({"run_id": "r"}, lambda *a, **k: {})
    assert sig is None


# -- gt-findings adapter (byte-identical reward mapping) --------------------

def test_gt_findings_maps_games_result() -> None:
    games = {
        "scoring": {"f1": 0.82, "precision": 0.8, "recall": 0.84,
                    "true_positives": 4, "false_positives": 1,
                    "false_negatives": 2},
        "blockchain": {"amount": 82.0, "wallet_id": "wallet-kiro-agent"},
        "gt_entries_count": 6,
    }
    sig = GtFindingsRewardSource().signal_or_none(
        {"run_id": "r", "graph_id": "g"}, _games_invoker(games))
    assert sig is not None
    assert sig.source_id == "gt-findings"
    assert sig.scalar == 0.82
    assert sig.reward_value == 82.0  # blockchain.amount wins
    assert sig.verdict == "rewarded"
    assert sig.wallet_id == "wallet-kiro-agent"
    assert sig.provenance["precision"] == 0.8
    assert sig.provenance["true_positives"] == 4
    assert sig.raw == games  # preserved for the byte-identical emitter


@pytest.mark.parametrize("wire", ["typed", "serialized"])
def test_gt_findings_accepts_typed_and_serialized_results(wire: str) -> None:
    payload = {
        "scoring": {"f1": 0.82, "precision": 0.8, "recall": 0.84},
        "blockchain": {"amount": 82.0, "wallet_id": "wallet-kiro-agent"},
        "gt_entries_count": 6,
    }
    result: Any = ToolResult(ok=True, data=payload)
    if wire == "serialized":
        result = result.model_dump(mode="json")

    sig = GtFindingsRewardSource().signal_or_none(
        {"run_id": "r", "graph_id": "g"}, _games_invoker(result))
    assert sig is not None
    assert sig.scalar == 0.82
    assert sig.reward_value == 82.0


def test_gt_findings_reward_falls_back_to_f1_times_100() -> None:
    games = {"scoring": {"f1": 0.5}, "blockchain": {}, "gt_entries_count": 3}
    sig = GtFindingsRewardSource().signal_or_none(
        {"graph_id": "g"}, _games_invoker(games))
    assert sig is not None
    assert sig.reward_value == 50.0
    assert sig.verdict == "rewarded"


@pytest.mark.parametrize(
    "blockchain",
    [
        {"status": "failed", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"status": "cancelled", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"status": "timeout", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"error": "mint_failed", "amount": 99.0, "wallet_id": "wallet-valid"},
    ],
)
def test_gt_findings_abstains_on_failed_nested_blockchain_evidence(
    blockchain: dict[str, object],
) -> None:
    games = {
        "scoring": {"f1": 0.99},
        "blockchain": blockchain,
        "gt_entries_count": 1,
    }
    assert GtFindingsRewardSource().signal_or_none(
        {"graph_id": "g"}, _games_invoker(ToolResult(ok=True, data=games)),
    ) is None


def test_gt_findings_zero_f1_with_gt_is_no_reward() -> None:
    # 0 detections WITH ground truth = recall 0 (false negatives) — a valuable
    # signal that MUST score, not abstain (bd:python-factory-hx5zc).
    games = {"scoring": {"f1": 0.0}, "blockchain": {}, "gt_entries_count": 4}
    sig = GtFindingsRewardSource().signal_or_none(
        {"graph_id": "g"}, _games_invoker(games))
    assert sig is not None
    assert sig.reward_value == 0.0
    assert sig.verdict == "no_reward"


def test_gt_findings_abstains_when_no_ground_truth() -> None:
    # No ground truth resolved (gt_entries_count == 0) → abstain. This replaces
    # the deleted is_rl_eligible security-skill allowlist with a data-driven gate.
    games = {"scoring": {"f1": 0.0}, "blockchain": {}, "gt_entries_count": 0}
    sig = GtFindingsRewardSource().signal_or_none(
        {"graph_id": "g"}, _games_invoker(games))
    assert sig is None


def test_gt_findings_abstains_when_gt_count_missing() -> None:
    # A games result lacking gt_entries_count is treated as no ground truth.
    games = {"scoring": {"f1": 0.9}, "blockchain": {"amount": 90.0}}
    sig = GtFindingsRewardSource().signal_or_none(
        {"graph_id": "g"}, _games_invoker(games))
    assert sig is None


def test_gt_findings_abstains_without_invoker() -> None:
    assert GtFindingsRewardSource().signal_or_none({"graph_id": "g"}, None) is None


def test_gt_findings_abstains_without_graph_id() -> None:
    # Chat turns carry no graph_id → gt-findings must abstain (llm-judge covers them).
    called = []
    sig = GtFindingsRewardSource().signal_or_none(
        {"run_id": "chat-1", "output_summary": "hi"},
        lambda *a, **k: called.append(a) or {})
    assert sig is None
    assert called == []  # never even calls games


# -- runtime.compute --------------------------------------------------------

def test_runtime_compute_returns_primary_signal() -> None:
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    rt = LearningRuntime(reg)
    games = {
        "scoring": {"f1": 0.7, "precision": 0.7, "recall": 0.7},
        "blockchain": {"amount": 70.0, "wallet_id": "w"},
        "gt_entries_count": 5,
    }
    out = rt.compute({"run_id": "r", "graph_id": "g"}, _games_invoker(games))
    assert out["source_id"] == "gt-findings"
    assert out["reward_value"] == 70.0
    assert out["verdict"] == "rewarded"
    assert out["scoring"]["f1"] == 0.7
    assert out["raw"] == games
    assert out["provenance"]["precision"] == 0.7
    assert len(out["signals"]) == 1


def test_runtime_compute_no_signal_is_neutral() -> None:
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    rt = LearningRuntime(reg)
    out = rt.compute({"run_id": "r"}, None)  # gt abstains without invoker
    assert out["source_id"] == ""
    assert out["reward_value"] == 0.0
    assert out["verdict"] == "no_reward"
    assert out["signals"] == []
