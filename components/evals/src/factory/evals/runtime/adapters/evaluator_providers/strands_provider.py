"""Strands-agents-evals provider — rail rider over the pinned SDK judges.

Wraps each SDK evaluator in a neutral adapter that converts neutral
``EvaluationData`` in and SDK ``EvaluationOutput`` back to neutral
``EvaluationOutput``. The Bedrock judge model id is injected into every SDK
evaluator. ``strands_evals`` is imported lazily inside ``build``.
"""
from __future__ import annotations

from typing import Any

from ..evaluator_factory import (
    EVALUATOR_REGISTRY,
    EvaluationData,
    EvaluationOutput,
    build_sdk_evaluator,
    validate_evaluator_names,
)
from .._judge_model import judge_model_id


class _StrandsEvaluator:
    """Neutral adapter around one SDK evaluator instance."""

    def __init__(self, name: str, sdk_evaluator: Any) -> None:
        self.name = name
        self._sdk = sdk_evaluator

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        from strands_evals.types.evaluation import EvaluationData as SdkData

        sdk_data = SdkData(
            input=data.input,
            actual_output=data.actual_output,
            expected_output=data.expected_output,
            actual_trajectory=data.actual_trajectory,
            actual_interactions=data.actual_interactions,
        )
        return [
            EvaluationOutput(
                float(out.score), bool(out.test_pass),
                str(out.reason or ""), str(getattr(out, "label", "") or ""),
            )
            for out in self._sdk.evaluate(sdk_data)
        ]


class StrandsProvider:
    """Provider (``framework="strands"``) exposing the full SDK judge vocabulary."""

    framework = "strands"

    def available(self) -> list[str]:
        return list(EVALUATOR_REGISTRY)

    def build(
        self, names: list[str], rubric: str = "",
        options: dict[str, Any] | None = None,
    ) -> list[_StrandsEvaluator]:
        del options  # strands SDK judges take no rail-level options
        validated = validate_evaluator_names(names)
        model_id = judge_model_id()
        return [
            _StrandsEvaluator(name, build_sdk_evaluator(name, model_id, rubric))
            for name in validated
        ]
