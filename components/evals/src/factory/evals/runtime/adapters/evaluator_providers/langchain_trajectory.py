"""agentevals trajectory provider — deterministic match + LLM judges.

``LangChainTrajectoryProvider`` (``framework="langchain_trajectory"``) exposes
four evaluator names over a message-list trajectory:

- ``trajectory_accuracy`` — reference-free LLM judge (uses the WITH_REFERENCE
  prompt + reference_outputs when an ``expected_trajectory`` is supplied).
- ``trajectory_match`` — DETERMINISTIC exact/ordered match, no Bedrock.
- ``tool_selection`` — LLM judge over tool-selection quality.
- ``custom`` — LLM judge driven by a caller-supplied rubric prompt.

agentevals / openevals / the judge model are imported lazily inside
``build``/``evaluate`` so importing this module never drags in an SDK.
"""
from __future__ import annotations

from typing import Any, Callable

from ..evaluator_factory import EvaluationData, EvaluationOutput
from .._judge_model import get_judge_model
from .langchain_provider import _to_output

_TRAJECTORY_ACCURACY = "trajectory_accuracy"
_TRAJECTORY_MATCH = "trajectory_match"
_TOOL_SELECTION = "tool_selection"
_CUSTOM = "custom"


class _TrajectoryLLMEvaluator:
    """LLM judge over a message-list trajectory (abstains without one)."""

    def __init__(
        self, name: str, judge_model: Any, prompt: Any,
        reference_prompt: Any | None = None,
    ) -> None:
        self.name = name
        self._model = judge_model
        self._prompt = prompt
        self._reference_prompt = reference_prompt
        self._cache: dict[bool, Callable[..., Any]] = {}

    def _judge_fn(self, with_reference: bool) -> Callable[..., Any]:
        if with_reference not in self._cache:
            from agentevals.trajectory.llm import create_trajectory_llm_as_judge

            prompt = self._reference_prompt if with_reference else self._prompt
            self._cache[with_reference] = create_trajectory_llm_as_judge(
                prompt=prompt, judge=self._model, continuous=True,
            )
        return self._cache[with_reference]

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        trajectory = data.actual_trajectory
        if not trajectory:
            return [EvaluationOutput(
                0.0, False,
                f"{self.name} requires actual_trajectory; abstained", "abstain",
            )]
        use_reference = bool(self._reference_prompt and data.expected_trajectory)
        judge = self._judge_fn(use_reference)
        if use_reference:
            result = judge(outputs=trajectory, reference_outputs=data.expected_trajectory)
        else:
            result = judge(outputs=trajectory)
        return [_to_output(self.name, result)]


class _TrajectoryMatchEvaluator:
    """Deterministic trajectory match (no LLM); abstains without both sides."""

    name = _TRAJECTORY_MATCH

    def __init__(self, evaluator_fn: Callable[..., Any]) -> None:
        self._eval = evaluator_fn

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        if not data.actual_trajectory or not data.expected_trajectory:
            return [EvaluationOutput(
                0.0, False,
                "trajectory_match requires actual_trajectory and "
                "expected_trajectory; abstained", "abstain",
            )]
        result = self._eval(
            outputs=data.actual_trajectory,
            reference_outputs=data.expected_trajectory,
        )
        raw = bool(result.get("score"))
        comment = str(result.get("comment") or "")
        return [EvaluationOutput(float(raw), raw, comment, _TRAJECTORY_MATCH)]


class LangChainTrajectoryProvider:
    """agentevals trajectory provider (``framework="langchain_trajectory"``)."""

    framework = "langchain_trajectory"
    _AVAILABLE = (_TRAJECTORY_ACCURACY, _TRAJECTORY_MATCH, _TOOL_SELECTION, _CUSTOM)

    def available(self) -> list[str]:
        return list(self._AVAILABLE)

    def build(
        self, names: list[str], rubric: str = "",
        options: dict[str, Any] | None = None,
    ) -> list:
        options = options or {}
        unknown = sorted({name for name in names if name not in self._AVAILABLE})
        if unknown:
            raise ValueError(
                f"langchain_trajectory provider does not support: {', '.join(unknown)}. "
                f"available: {', '.join(self._AVAILABLE)}"
            )
        built: list[Any] = []
        judge_model: Any | None = None
        for name in names:
            if name == _TRAJECTORY_MATCH:
                from agentevals.trajectory.match import create_trajectory_match_evaluator

                built.append(_TrajectoryMatchEvaluator(create_trajectory_match_evaluator(
                    trajectory_match_mode=options.get("match_mode", "strict"),
                    tool_args_match_mode=options.get("tool_args_mode", "exact"),
                )))
                continue
            if judge_model is None:
                judge_model = get_judge_model()
            built.append(self._llm_evaluator(name, rubric, judge_model))
        return built

    @staticmethod
    def _llm_evaluator(name: str, rubric: str, judge_model: Any) -> _TrajectoryLLMEvaluator:
        if name == _TRAJECTORY_ACCURACY:
            from agentevals.trajectory.llm import (
                TRAJECTORY_ACCURACY_PROMPT,
                TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE,
            )
            return _TrajectoryLLMEvaluator(
                name, judge_model, TRAJECTORY_ACCURACY_PROMPT,
                TRAJECTORY_ACCURACY_PROMPT_WITH_REFERENCE,
            )
        if name == _TOOL_SELECTION:
            from openevals.prompts import TOOL_SELECTION_PROMPT

            return _TrajectoryLLMEvaluator(name, judge_model, TOOL_SELECTION_PROMPT)
        # _CUSTOM
        if not rubric:
            raise ValueError("langchain_trajectory custom evaluator requires a rubric")
        # Guarantee the trajectory reaches the judge even if the rubric omits the
        # placeholder (a bare rubric would otherwise judge blind).
        prompt = rubric if "{outputs}" in rubric else (
            rubric + "\n\n<trajectory>\n{outputs}\n</trajectory>"
        )
        return _TrajectoryLLMEvaluator(name, judge_model, prompt)
