"""LangChain-backed output-level LLM-as-judge provider — openevals.

``LangChainProvider`` (``framework="langchain"``): OUTPUT-level openevals
LLM-as-judge over input/output/reference text. Five canned judges carry their
own rubric; the ``custom`` judge takes a caller-supplied rubric f-string.

The trajectory rider lives in ``langchain_trajectory.py``. openevals and the
Bedrock judge model are imported lazily inside ``build`` so importing this
module never drags in LangChain.
"""
from __future__ import annotations

from typing import Any, Callable

from ..evaluator_factory import EvaluationData, EvaluationOutput
from .._judge_model import get_judge_model

# openevals prebuilt-prompt names → module attribute names (lazy-resolved).
_OPENEVALS_PROMPTS = {
    "conciseness": "CONCISENESS_PROMPT",
    "correctness": "CORRECTNESS_PROMPT",
    "answer_relevance": "ANSWER_RELEVANCE_PROMPT",
    "hallucination": "HALLUCINATION_PROMPT",
    "helpfulness": "RAG_HELPFULNESS_PROMPT",
}
_CUSTOM = "custom"

# Appended to a custom rubric that omits placeholders so the judge always sees
# the evidence it is scoring (a bare "score 1.0 if X" rubric otherwise judges
# blind — openevals only injects params the prompt references).
_EVIDENCE_BLOCK = "\n\n<input>\n{inputs}\n</input>\n<output>\n{outputs}\n</output>"


def _ensure_evidence(rubric: str) -> str:
    """Guarantee the judged input/output reach the prompt regardless of phrasing."""
    return rubric if "{outputs}" in rubric else rubric + _EVIDENCE_BLOCK


def _to_output(name: str, result: dict[str, Any]) -> EvaluationOutput:
    """Map an openevals judge result to a neutral output."""
    raw = result.get("score")
    score = float(raw) if isinstance(raw, (int, float)) and not isinstance(raw, bool) else 0.0
    comment = str(result.get("comment") or result.get("reasoning") or "")
    return EvaluationOutput(score, score >= 0.5, comment, name)


class _OpenEvalsEvaluator:
    """Neutral adapter around an openevals output-level judge callable."""

    def __init__(self, name: str, judge_fn: Callable[..., Any]) -> None:
        self.name = name
        self._judge = judge_fn

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        result = self._judge(
            inputs=data.input,
            outputs=data.actual_output,
            reference_outputs=data.expected_output,
        )
        return [_to_output(self.name, result)]


class LangChainProvider:
    """openevals output-level LLM-as-judge (``framework="langchain"``)."""

    framework = "langchain"

    def available(self) -> list[str]:
        return [*_OPENEVALS_PROMPTS, _CUSTOM]

    def build(
        self, names: list[str], rubric: str = "",
        options: dict[str, Any] | None = None,
    ) -> list[_OpenEvalsEvaluator]:
        del options  # output-level judges take no rail-level options
        supported = {*_OPENEVALS_PROMPTS, _CUSTOM}
        unknown = sorted({name for name in names if name not in supported})
        if unknown:
            raise ValueError(
                f"langchain provider does not support: {', '.join(unknown)}. "
                f"available: {', '.join(sorted(supported))}"
            )
        from openevals import prompts as p
        from openevals.llm import create_llm_as_judge

        judge = get_judge_model()
        built: list[_OpenEvalsEvaluator] = []
        for name in names:
            if name == _CUSTOM:
                if not rubric:
                    raise ValueError("langchain custom evaluator requires a rubric")
                judge_fn = create_llm_as_judge(
                    prompt=_ensure_evidence(rubric), judge=judge, continuous=True, feedback_key=_CUSTOM,
                )
            else:
                judge_fn = create_llm_as_judge(
                    prompt=getattr(p, _OPENEVALS_PROMPTS[name]),
                    judge=judge, continuous=True, feedback_key=name,
                )
            built.append(_OpenEvalsEvaluator(name, judge_fn))
        return built
