"""Native MCP v2 tools for experiment serialization."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, fail, operational

from .contracts.experiment_serialization import (
    ListSavedExperimentsInput, LoadExperimentInput, LoadExperimentOutput,
    SaveExperimentInput, SaveExperimentOutput, SavedExperimentsOutput,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register serialization tools with flat typed ingress."""

    @mcp.tool()
    @operational(input_model=SaveExperimentInput, output_model=SaveExperimentOutput)
    def evals_save_experiment(cases: list[dict[str, Any]], evaluator_names: list[str], filename: str, rubric: str = "", experiment_name: str = "") -> ToolResult[SaveExperimentOutput]:
        """Save an experiment configuration to JSON."""
        from ..runtime.ports import EvalCase, ExperimentConfig
        eval_cases = [EvalCase(id=case.get("id", f"case-{index}"), name=case.get("name", f"case-{index}"), input=case.get("input", {}), expected=case.get("expected_output"), metadata=case.get("metadata", {})) for index, case in enumerate(cases)]
        config = ExperimentConfig(cases=eval_cases, evaluator_names=evaluator_names, rubric=rubric, name=experiment_name or filename)
        try:
            return SaveExperimentOutput(**get_runtime().save_experiment(config, filename))
        except RuntimeError as exc:
            return fail(str(exc))

    @mcp.tool()
    @operational(input_model=LoadExperimentInput, output_model=LoadExperimentOutput)
    def evals_load_experiment(filename: str) -> ToolResult[LoadExperimentOutput]:
        """Load an experiment configuration from JSON."""
        try:
            config = get_runtime().load_experiment(filename)
        except (RuntimeError, FileNotFoundError) as exc:
            return fail(str(exc))
        cases = [{"id": case.id, "name": case.name, "input": case.input, "expected": case.expected} for case in config.cases]
        return LoadExperimentOutput(name=config.name, cases=cases, evaluator_names=config.evaluator_names, case_count=len(cases))

    @mcp.tool()
    @deterministic(input_model=ListSavedExperimentsInput, output_model=SavedExperimentsOutput)
    def evals_list_saved_experiments() -> ToolResult[SavedExperimentsOutput]:
        """List all saved experiment files."""
        experiments = get_runtime().list_saved_experiments()
        return SavedExperimentsOutput(experiments=experiments, count=len(experiments))
