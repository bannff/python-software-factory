"""Metadata catalog derived from the canonical LLMAJ alias registry."""
from __future__ import annotations

from typing import Any

from .evaluator_factory import EVALUATOR_REGISTRY

_DESCRIPTIONS = {
    "output": "Flexible LLM-based evaluation with custom rubrics",
    "helpfulness": "Evaluate response helpfulness from user perspective",
    "faithfulness": "Assess factual accuracy and groundedness",
    "coherence": "Assess logical consistency of responses",
    "conciseness": "Evaluate response brevity and directness",
    "harmfulness": "Detect harmful or unsafe content in responses",
    "response_relevance": "Assess relevance of response to the input query",
    "tool_selection": "Evaluate whether correct tools were selected",
    "tool_parameter": "Evaluate accuracy of tool parameters",
    "trajectory": "Assess sequence of actions and tool usage patterns",
    "interactions": "Analyze conversation patterns and interaction quality",
    "goal_success": "Determine if user goals were successfully achieved",
}
_COMPUTATIONAL = {
    "can_auroc": "Area under the ROC curve for CAN failure prediction",
    "can_auprc": "Area under the precision-recall curve for CAN failure prediction",
    "can_brier": "Brier calibration score for CAN failure prediction",
    "can_lead_time": "Mean samples from earliest detection to failure onset",
    "can_false_alarm": "False alarm rate for CAN failure prediction",
    "can_episode_recall": "Fraction of contiguous failure runs detected",
    "can_distribution_similarity": "Distribution similarity for real and synthetic CAN data",
    "can_temporal_coherence": "Lag-1 autocorrelation match for CAN signals",
    "can_statistical_fidelity": "Normalized per-signal statistical fidelity",
    "can_mode_coverage": "Fraction of real signal ranges covered by synthetic data",
}


def get_available_evaluators() -> list[dict[str, Any]]:
    """Return LLMAJ metadata plus the separate computational evaluator route."""
    llmaj = [
        {
            "name": alias,
            "class": spec.class_name,
            "level": spec.sdk_level.name if spec.sdk_level else None,
            "sdk_level": spec.sdk_level.value if spec.sdk_level else None,
            "evidence_kind": spec.evidence_kind,
            "description": _DESCRIPTIONS[alias],
            "requires_rubric": spec.requires_rubric,
        }
        for alias, spec in EVALUATOR_REGISTRY.items()
    ]
    computational = [
        {
            "name": name,
            "class": f"computational.{name}",
            "level": "COMPUTATIONAL",
            "description": description,
            "requires_rubric": False,
        }
        for name, description in _COMPUTATIONAL.items()
    ]
    return llmaj + computational
