"""Framework-neutral evaluator registry and local evaluator models."""
from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any

from ._judge_model import judge_model_id

DEFAULT_RUBRIC = (
    "Score 1.0 if the response is accurate, complete, and helpful. "
    "Score 0.5 if partially correct. Score 0.0 if incorrect or unhelpful."
)


class EvaluationLevel(str, Enum):
    TRACE_LEVEL = "Trace"
    TOOL_LEVEL = "ToolCall"
    SESSION_LEVEL = "Session"


@dataclass(frozen=True)
class EvaluationData:
    input: str
    actual_output: str
    expected_output: str | None = None
    actual_trajectory: Any | None = None
    actual_interactions: list[dict[str, Any]] | None = None
    expected_trajectory: list[Any] | None = None


@dataclass(frozen=True)
class EvaluationOutput:
    score: float
    test_pass: bool
    reason: str
    label: str = ""

    def model_dump(self, mode: str = "json") -> dict[str, Any]:
        del mode
        return asdict(self)


@dataclass(frozen=True)
class EvaluatorSpec:
    class_name: str
    evidence_kind: str
    sdk_level: EvaluationLevel | None = None
    requires_rubric: bool = False
    sdk_class_name: str = ""


# One alias vocabulary, two framework bindings: `class_name` is the local
# deterministic label; `sdk_class_name` is the pinned strands-agents-evals class.
# Adding a framework is data (a new column here), never a parallel factory.
EVALUATOR_REGISTRY: dict[str, EvaluatorSpec] = {
    "output": EvaluatorSpec("LocalOutputEvaluator", "output", requires_rubric=True, sdk_class_name="OutputEvaluator"),
    "helpfulness": EvaluatorSpec("LocalHelpfulnessEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="HelpfulnessEvaluator"),
    "faithfulness": EvaluatorSpec("LocalFaithfulnessEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="FaithfulnessEvaluator"),
    "coherence": EvaluatorSpec("LocalCoherenceEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="CoherenceEvaluator"),
    "conciseness": EvaluatorSpec("LocalConcisenessEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="ConcisenessEvaluator"),
    "harmfulness": EvaluatorSpec("LocalHarmfulnessEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="HarmfulnessEvaluator"),
    "response_relevance": EvaluatorSpec("LocalResponseRelevanceEvaluator", "trace", EvaluationLevel.TRACE_LEVEL, sdk_class_name="ResponseRelevanceEvaluator"),
    "tool_selection": EvaluatorSpec("LocalToolSelectionEvaluator", "tool", EvaluationLevel.TOOL_LEVEL, sdk_class_name="ToolSelectionAccuracyEvaluator"),
    "tool_parameter": EvaluatorSpec("LocalToolParameterEvaluator", "tool", EvaluationLevel.TOOL_LEVEL, sdk_class_name="ToolParameterAccuracyEvaluator"),
    "trajectory": EvaluatorSpec("LocalTrajectoryEvaluator", "trajectory", requires_rubric=True, sdk_class_name="TrajectoryEvaluator"),
    "interactions": EvaluatorSpec("LocalInteractionsEvaluator", "interactions", requires_rubric=True, sdk_class_name="InteractionsEvaluator"),
    "goal_success": EvaluatorSpec("LocalGoalSuccessEvaluator", "session", EvaluationLevel.SESSION_LEVEL, sdk_class_name="GoalSuccessRateEvaluator"),
}

EVALUATOR_FRAMEWORKS = ("strands",)
OUTPUT_LEVEL_EVALUATORS = frozenset({"output"})
TRACE_LEVEL_EVALUATORS = frozenset(name for name, spec in EVALUATOR_REGISTRY.items() if spec.sdk_level == EvaluationLevel.TRACE_LEVEL)
TOOL_LEVEL_EVALUATORS = frozenset(name for name, spec in EVALUATOR_REGISTRY.items() if spec.sdk_level == EvaluationLevel.TOOL_LEVEL)
SESSION_LEVEL_EVALUATORS = frozenset(name for name, spec in EVALUATOR_REGISTRY.items() if spec.sdk_level == EvaluationLevel.SESSION_LEVEL)
TRAJECTORY_EVALUATORS = frozenset(name for name, spec in EVALUATOR_REGISTRY.items() if spec.evidence_kind == "trajectory")
INTERACTIONS_EVALUATORS = frozenset(name for name, spec in EVALUATOR_REGISTRY.items() if spec.evidence_kind == "interactions")


def validate_evaluator_names(names: list[str]) -> tuple[str, ...]:
    if not names:
        raise ValueError("evaluator_names must contain at least one evaluator")
    unknown = sorted({name for name in names if name not in EVALUATOR_REGISTRY})
    if unknown:
        raise ValueError(f"unknown evaluator aliases: {', '.join(unknown)}")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        raise ValueError(f"duplicate evaluator aliases: {', '.join(duplicates)}")
    return tuple(names)


def needs_trace(evaluator_names: list[str]) -> bool:
    return any(name not in OUTPUT_LEVEL_EVALUATORS for name in validate_evaluator_names(evaluator_names))


def get_evaluator_class(alias: str, framework: str = "strands") -> type[Any]:
    """Resolve one validated alias to its raw strands-agents-evals class."""
    validate_evaluator_names([alias])
    if framework == "strands":
        from strands_evals import evaluators
        return getattr(evaluators, EVALUATOR_REGISTRY[alias].sdk_class_name)
    raise ValueError(f"unknown evaluator framework: {framework}")


def evaluator_classes(framework: str = "strands") -> list[type[Any]]:
    """Return every evaluator class for a framework in canonical alias order."""
    return [get_evaluator_class(alias, framework) for alias in EVALUATOR_REGISTRY]


def alias_for_evaluator(evaluator: Any, framework: str = "strands") -> str:
    """Return the canonical alias for an instantiated strands SDK evaluator."""
    if framework != "strands":
        raise ValueError(f"unknown evaluator framework: {framework}")
    class_name = type(evaluator).__name__
    for alias, spec in EVALUATOR_REGISTRY.items():
        if spec.sdk_class_name == class_name:
            return alias
    raise ValueError(f"unsupported evaluator class: {class_name}")


def build_sdk_evaluator(alias: str, model: Any, rubric: str = "") -> Any:
    """Instantiate ONE raw strands-agents-evals judge with a judge model.

    Single source of the alias -> SDK class + rubric + model kwarg assembly,
    shared by the provider rail (``StrandsProvider.build``) and the SDK
    Experiment path (``build_evaluators``). ``model`` is REQUIRED so judge-model
    injection can never silently diverge to the SDK's cross-region default.
    """
    spec = EVALUATOR_REGISTRY[alias]
    sdk_class = get_evaluator_class(alias, "strands")
    kwargs: dict[str, Any] = {"name": alias, "model": model}
    if spec.requires_rubric:
        kwargs["rubric"] = rubric or DEFAULT_RUBRIC
    return sdk_class(**kwargs)


def build_evaluators(
    names: list[str], rubric: str = "", framework: str = "strands",
) -> list[Any]:
    """Instantiate RAW strands-agents-evals judges for validated aliases.

    Consumed by the SDK Experiment path (experiment/simulator/serialization/
    tool-chaos adapters). The ``framework`` kwarg is retained for call-site
    compatibility but ``strands`` is the only binding — direct-evaluation
    framework selection now lives on the provider rail
    (``evaluator_providers``), not here. The configured Bedrock judge model is
    injected into every judge via ``build_sdk_evaluator``.
    """
    validated = validate_evaluator_names(names)
    if framework != "strands":
        raise ValueError(f"unknown evaluator framework: {framework}")
    model = judge_model_id()
    return [build_sdk_evaluator(name, model, rubric) for name in validated]
