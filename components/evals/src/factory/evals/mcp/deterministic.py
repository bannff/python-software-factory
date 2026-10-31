"""Typed deterministic MCP tools for the Evals brick."""
from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic

from .contracts.deterministic import (
    CapabilitiesOutput, ConfigSchemaOutput, EmptyInput, HealthOutput,
    HealthRunnerOutput, ListRunsInput, RunIdInput, RunOutput, RunsOutput,
    ScoreGtInput, ScoreGtOutput, SuiteIdInput, SuiteOutput, SuitesOutput,
    _MAX_SCORE_EVIDENCE_ITEMS,
)

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register deterministic Evals tools with flat typed ingress."""

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        runtime = get_runtime()
        return CapabilitiesOutput(name="evals", version="2.0.0", backends=runtime.available_backends(), features=["benchmark_suites", "eval_runs", "metrics_collection", "result_comparison", "strands_experiments", "llm_as_judge_evaluators", "direct_evaluator_invocation", "multi_evaluator_batch", "experiment_generation", "declarative_agent_config", "actor_simulation", "experiment_serialization", "eval_sop_workflow"], mcp_resources=["evals://schemas/*", "evals://docs/*", "evals://runs", "evals://metrics", "evals://evaluators", "evals://sop/sessions"], mcp_prompts=["create_eval", "run_eval", "analyze_results", "compare_runs", "evaluate_output", "eval_sop"])

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        health = get_runtime().health_check()
        runners = {key: HealthRunnerOutput(healthy=value.healthy, backend=value.backend) for key, value in health.items()}
        return HealthOutput(healthy=all(item.healthy for item in health.values()) if health else True, runners=runners)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ConfigSchemaOutput(type="object", properties={"backend": {"type": "string", "enum": ["custom", "strands"], "description": "Evaluation backend adapter"}})

    @mcp.tool()
    @deterministic(input_model=SuiteIdInput, output_model=SuiteOutput)
    def evals_get_suite(suite_id: str) -> ToolResult[SuiteOutput]:
        suite = get_runtime().get_runner().get_suite(suite_id)
        return SuiteOutput(found=False) if not suite else SuiteOutput(found=True, id=suite.id, name=suite.name, description=suite.description, case_count=len(suite.cases))

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=SuitesOutput)
    def evals_list_suites() -> ToolResult[SuitesOutput]:
        suites = get_runtime().get_runner().list_suites()
        return SuitesOutput(suites=[{"id": item.id, "name": item.name, "case_count": len(item.cases)} for item in suites], count=len(suites))

    @mcp.tool()
    @deterministic(input_model=RunIdInput, output_model=RunOutput)
    def evals_get_run(run_id: str) -> ToolResult[RunOutput]:
        run = get_runtime().get_runner().get_run(run_id)
        return RunOutput(found=False) if not run else RunOutput(found=True, id=run.id, suite_id=run.suite_id, status=run.status, summary=run.summary, result_count=len(run.results))

    @mcp.tool()
    @deterministic(input_model=ListRunsInput, output_model=RunsOutput)
    def evals_list_runs(suite_id: str | None = None) -> ToolResult[RunsOutput]:
        runs = get_runtime().get_runner().list_runs(suite_id)
        return RunsOutput(runs=[{"id": item.id, "suite_id": item.suite_id, "status": item.status} for item in runs], count=len(runs))

    @mcp.tool()
    @deterministic(input_model=ScoreGtInput, output_model=ScoreGtOutput)
    def evals_score_gt(findings: list[dict[str, Any]], gt_entries: list[dict[str, Any]], match_on: list[str] | None = None) -> ToolResult[ScoreGtOutput]:
        from ..runtime.gt_scorer import score
        scored = score(findings, gt_entries) if match_on is None else score(findings, gt_entries, match_on=tuple(match_on))
        for key in ("matched", "missed", "false_positives"):
            evidence = scored.get(key, [])
            scored[key] = evidence[:_MAX_SCORE_EVIDENCE_ITEMS]
        return ScoreGtOutput(**scored)
