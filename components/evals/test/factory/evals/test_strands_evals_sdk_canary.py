"""Import-only compatibility canary for the pinned Strands Evals SDK.

This test deliberately verifies public API availability without constructing an
agent, invoking a model, or running a simulation.
"""
from __future__ import annotations

from importlib.metadata import version


def test_pinned_strands_evals_feature_surface_is_importable() -> None:
    """Pin supplies the SDK-native simulation, safety, and multimodal APIs."""
    from strands_evals.chaos import (
        ChaosCase, ChaosExperiment, ChaosPlugin, CorruptValues, ExecutionError,
        NetworkError, RemoveFields, Timeout, TruncateFields, ValidationError,
    )
    from strands_evals.evaluators import (
        MultimodalCorrectnessEvaluator,
        MultimodalFaithfulnessEvaluator,
        MultimodalInstructionFollowingEvaluator,
        MultimodalOverallQualityEvaluator,
    )
    from strands_evals.experimental.redteam import (
        AdversarialCaseGenerator,
        CrescendoStrategy,
        RedTeamExperiment,
    )
    from strands_evals.simulation.tool_simulator import StateRegistry, ToolSimulator
    from strands_evals.types import ImageData, MultimodalInput

    assert version("strands-agents-evals") >= "1.0.0"
    assert all((
        StateRegistry,
        ToolSimulator,
        ChaosCase,
        ChaosExperiment,
        ChaosPlugin,
        Timeout,
        NetworkError,
        ExecutionError,
        ValidationError,
        TruncateFields,
        RemoveFields,
        CorruptValues,
        AdversarialCaseGenerator,
        CrescendoStrategy,
        RedTeamExperiment,
        ImageData,
        MultimodalInput,
        MultimodalCorrectnessEvaluator,
        MultimodalFaithfulnessEvaluator,
        MultimodalInstructionFollowingEvaluator,
        MultimodalOverallQualityEvaluator,
    ))


def test_experiment_runner_consumes_native_single_flattened_report(monkeypatch) -> None:
    """Execute the pinned SDK call shape without constructing a model."""
    from strands_evals.evaluators.evaluator import Evaluator
    from strands_evals.types import EvaluationOutput
    from factory.evals.runtime.adapters import experiment_runner
    from factory.evals.runtime.ports import EvalCase, ExperimentConfig

    class FixedEvaluator(Evaluator[str, str]):
        def evaluate(self, _data):
            passed = self.get_name() == "first"
            return [EvaluationOutput(
                score=float(passed), test_pass=passed,
                reason=self.get_name(), label=self.get_name(),
            )]

    monkeypatch.setattr(
        experiment_runner, "build_evaluators",
        lambda *_a, **_k: [FixedEvaluator(name="first"), FixedEvaluator(name="second")],
    )
    monkeypatch.setattr(
        experiment_runner, "build_agent_fn", lambda *_a: lambda case: f"answer:{case.name}",
    )
    config = ExperimentConfig(
        name="call-shape", evaluator_names=["first", "second"],
        cases=[
            EvalCase(id="a", name="a", input="one"),
            EvalCase(id="b", name="b", input="two"),
        ],
    )
    report = experiment_runner.run_strands_experiment(config)
    assert [row["evaluator"] for row in report.case_results] == [
        "first", "first", "second", "second",
    ]
    assert [row["score"] for row in report.case_results] == [1.0, 1.0, 0.0, 0.0]
    assert [row["detailed_results"][0]["label"] for row in report.case_results] == [
        "first", "first", "second", "second",
    ]
    assert report.summary == {
        "overall_score": 0.5,
        "pass_rate": 0.5,
        "total_cases": 2,
        "total_evaluation_rows": 4,
    }
