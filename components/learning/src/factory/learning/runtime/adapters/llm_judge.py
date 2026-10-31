"""LLM-judge reward source (built-in) — domain-agnostic quality reward.

Scores an arbitrary work output (e.g. a chat turn's response) via the
evals brick's ``evals_evaluate_multi`` LLM-judge rubric, mapping the
aggregate 0..1 score onto a neutral :class:`RewardSignal`. This is what
lets the MAIN chat agent — and any non-finding work — earn reward, closing
the "everything is scoreable" gap (bd python-factory-pfvo9, slice 2).

Cheap-to-abstain (meta-architect HARD NOTE): it returns ``None`` unless the
run context carries a non-trivial ``output_summary`` to judge, so trivial
turns never pay for an LLM eval. Broader sampling/gating is a follow-up.
No cross-brick import — it reaches evals purely through the MCP invoker.
"""

from __future__ import annotations

import logging
from math import isfinite
from typing import Any, Callable

from ..models import RewardSignal
from .mcp_result import successful_data, validate_evals_result

logger = logging.getLogger(__name__)

_TOOL = "evals_evaluate_multi"
# OUTPUT-level LLM-judge framework + evaluators that score input/output text
# directly (openevals RAG_HELPFULNESS + ANSWER_RELEVANCE). The prior default
# ("helpfulness","coherence" over the fake local path) produced a constant
# 0.0 reward for every chat turn (#719); these are real, text-scoreable.
_DEFAULT_FRAMEWORK = "langchain"
_DEFAULT_EVALUATORS = ["helpfulness", "answer_relevance"]
# Below this many chars of output we abstain — keeps cost off trivial turns.
_MIN_OUTPUT_CHARS = 40


class LlmJudgeRewardSource:
    """Judges a work output via evals and maps the score to a RewardSignal."""

    source_id = "llm-judge"

    def signal_or_none(
        self, run_ctx: dict[str, Any], invoker: Callable[..., Any] | None,
    ) -> RewardSignal | None:
        """Score ``output_summary`` via the LLM judge; abstain if trivial."""
        if invoker is None:
            return None
        output = str(run_ctx.get("output_summary") or run_ctx.get("text") or "")
        if len(output.strip()) < _MIN_OUTPUT_CHARS:
            return None  # cheap abstain — nothing worth judging
        input_text = str(run_ctx.get("input_summary") or "")
        evaluators = _resolve_evaluators(run_ctx)
        framework = str(run_ctx.get("judge_framework") or _DEFAULT_FRAMEWORK)
        try:
            result = invoker(
                _TOOL,
                input_text=input_text,
                output_text=output,
                evaluator_names=evaluators,
                framework=framework,
            )
        except Exception as exc:  # never raise into the engine loop
            logger.warning(
                "llm-judge evaluation failed error_type=%s",
                type(exc).__name__,
            )
            return None
        normalized = successful_data(
            result, allow_legacy=True, validator=validate_evals_result,
        )
        score = _avg_score(normalized)
        if score is None or normalized is None:
            return None
        return RewardSignal.from_scalar(
            self.source_id,
            score,
            provenance={
                "evaluators": evaluators,
                "framework": framework,
                "input_chars": len(input_text),
                "output_chars": len(output),
            },
            raw={"scoring": {"f1": score}, "evals": normalized},
        )


def _resolve_evaluators(run_ctx: dict[str, Any]) -> list[str]:
    """Evaluator list from run context, else the OUTPUT-level defaults."""
    configured = run_ctx.get("judge_evaluators")
    if isinstance(configured, (list, tuple)):
        names = [str(name) for name in configured if str(name).strip()]
        if names:
            return names
    return list(_DEFAULT_EVALUATORS)


def _avg_score(result: Any) -> float | None:
    """Pull a 0..1 aggregate score from successful typed Evals egress."""
    result = successful_data(
        result, allow_legacy=True, validator=validate_evals_result,
    )
    if result is None:
        return None
    for key in ("avg_score", "average_score", "score", "pass_rate"):
        v = result.get(key)
        if _valid_score(v):
            return float(v)
    for nest in ("aggregate", "summary"):
        sub = result.get(nest)
        if isinstance(sub, dict):
            for key in ("avg_score", "average_score", "score", "pass_rate"):
                v = sub.get(key)
                if _valid_score(v):
                    return float(v)
    return None


def _valid_score(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and isfinite(float(value))
        and 0.0 <= float(value) <= 1.0
    )


__all__ = ["LlmJudgeRewardSource"]
