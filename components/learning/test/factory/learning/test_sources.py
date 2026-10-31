"""Per-source reward-adapter tests: llm-judge, user-feedback, telemetry, and
the signed-scalar model (bd python-factory-pfvo9). Registry / gt-findings /
runtime.compute core tests live in test_core.py."""

from __future__ import annotations

import json

import pytest

from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.adapters.llm_judge import LlmJudgeRewardSource
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.mcp_utils.interface import ToolResult


def _judge_invoker(score: float):
    def _invoke(tool: str, **kwargs):
        assert tool == "evals_evaluate_multi"
        return {"aggregate": {"avg_score": score, "pass_rate": 1.0}}
    return _invoke


# -- llm-judge adapter (chat-turn / non-finding reward) ---------------------

def test_llm_judge_scores_chat_output() -> None:
    ctx = {
        "run_id": "chat-1",
        "input_summary": "How do I reverse a list in Python?",
        "output_summary": "Use list slicing: my_list[::-1] returns a reversed copy.",
    }
    sig = LlmJudgeRewardSource().signal_or_none(ctx, _judge_invoker(0.9))
    assert sig is not None
    assert sig.source_id == "llm-judge"
    assert sig.scalar == 0.9
    assert sig.reward_value == 90.0
    assert sig.verdict == "rewarded"
    assert sig.provenance["evaluators"] == ["helpfulness", "answer_relevance"]
    assert sig.provenance["framework"] == "langchain"


@pytest.mark.parametrize("wire", ["typed", "serialized"])
def test_llm_judge_accepts_typed_and_serialized_results(wire: str) -> None:
    payload = {"aggregate": {"avg_score": 0.9, "pass_rate": 1.0}}
    result = ToolResult(ok=True, data=payload)
    if wire == "serialized":
        result = result.model_dump(mode="json")

    sig = LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "A" * 50}, _judge_invoker_result(result)
    )
    assert sig is not None
    assert sig.scalar == 0.9
    assert sig.reward_value == 90.0
    json.dumps(sig.raw, ensure_ascii=False, allow_nan=False)


def test_llm_judge_abstains_when_score_is_missing() -> None:
    result = {"aggregate": {"total_evaluators": 1}}
    assert LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "A" * 50}, _judge_invoker_result(result)
    ) is None


def _judge_invoker_result(result: dict):
    def _invoke(tool: str, **kwargs):
        assert tool == "evals_evaluate_multi"
        return result
    return _invoke


def test_llm_judge_abstains_on_trivial_output() -> None:
    sig = LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "ok"}, _judge_invoker(0.9)
    )
    assert sig is None  # below the min-output gate → cheap abstain


def test_llm_judge_abstains_without_invoker() -> None:
    ctx = {"output_summary": "a" * 100}
    assert LlmJudgeRewardSource().signal_or_none(ctx, None) is None


def test_llm_judge_preserves_explicit_zero_score() -> None:
    sig = LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "A" * 50}, _judge_invoker(0.0)
    )
    assert sig is not None
    assert sig.scalar == 0.0
    assert sig.verdict == "no_reward"


def test_llm_judge_accepts_top_level_pass_rate() -> None:
    sig = LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "A" * 50},
        _judge_invoker_result({"pass_rate": 0.73}),
    )
    assert sig is not None
    assert sig.scalar == 0.73


def test_llm_judge_abstains_on_evaluator_error_even_with_score() -> None:
    sig = LlmJudgeRewardSource().signal_or_none(
        {"output_summary": "A" * 50},
        _judge_invoker_result({"error": "partial failure", "aggregate": {"avg_score": 0.9}}),
    )
    assert sig is None


def test_runtime_routes_chat_turn_to_llm_judge() -> None:
    # gt-findings abstains (no graph_id); llm-judge wins.
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(LlmJudgeRewardSource())
    rt = LearningRuntime(reg)

    def invoke(tool: str, **kwargs):
        if tool == "evals_evaluate_multi":
            return {"aggregate": {"avg_score": 0.8}}
        raise AssertionError(f"gt should not call games on a chat turn: {tool}")

    out = rt.compute(
        {"run_id": "chat-1",
         "output_summary": "A reasonably detailed and helpful answer here."},
        invoke)
    assert out["source_id"] == "llm-judge"
    assert out["reward_value"] == 80.0
    assert out["verdict"] == "rewarded"
