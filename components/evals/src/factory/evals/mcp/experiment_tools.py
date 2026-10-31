"""Native MCP v2 tools for Strands experiment execution and result retrieval."""
from __future__ import annotations

import uuid
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, deterministic, fail, get_service, operational

from .contracts.experiment_serialization import (
    EvaluatorsOutput, GenerateExperimentInput, GeneratedExperimentOutput,
    GetRunResultInput, ListEvaluatorsInput, ListRunResultsInput,
    PersistenceOutput, RunExperimentInput, RunExperimentOutput, RunResultOutput,
    RunResultsOutput,
)
from ..runtime.run_record_contract import build_run_request

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def _persist(request: dict[str, Any]) -> PersistenceOutput:
    """Forward one retryable request through the canonical Evals writer."""
    invoker = get_service("tool_invoker")
    if invoker is None:
        return PersistenceOutput(persisted=False, reason="no tool_invoker")
    try:
        result = invoker("evals_record_run", **request)
    except Exception as exc:  # noqa: BLE001 — execution result remains available
        return PersistenceOutput(persisted=False, reason=str(exc))
    envelope = result if isinstance(result, ToolResult) else ToolResult.model_validate(result)
    if not envelope.ok or envelope.data is None:
        return PersistenceOutput(persisted=False, reason=envelope.error or "record_run_failed")
    data = envelope.data.model_dump() if hasattr(envelope.data, "model_dump") else envelope.data
    return PersistenceOutput.model_validate(data) if isinstance(data, dict) else PersistenceOutput(persisted=False, reason="invalid record_run data")


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register experiment tools with flat typed ingress."""

    @mcp.tool()
    @deterministic(input_model=ListEvaluatorsInput, output_model=EvaluatorsOutput)
    def evals_list_evaluators() -> ToolResult[EvaluatorsOutput]:
        """List available Strands LLMAJ evaluators and their config."""
        evaluators = get_runtime().list_evaluators()
        return EvaluatorsOutput(evaluators=evaluators, count=len(evaluators))

    @mcp.tool()
    @operational(input_model=RunExperimentInput, output_model=RunExperimentOutput)
    def evals_run_experiment(
        cases: list[dict[str, Any]], evaluator_names: list[str] | None = None,
        rubric: str = "", model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_prompt: str = "You are a helpful assistant.", temperature: float = 0.1,
        experiment_name: str = "experiment", run_id: str | None = None,
        persist_only: bool = False, record_run_request: dict[str, Any] | None = None,
    ) -> ToolResult[RunExperimentOutput]:
        """Run an experiment or retry its canonical persistence request."""
        if persist_only:
            if not run_id or not record_run_request or record_run_request.get("run_id") != run_id:
                return fail("persist_only requires matching run_id and record_run_request")
            return RunExperimentOutput(run_id=run_id, record_run_request=record_run_request, persistence=_persist(record_run_request))
        from ..runtime.ports import EvalAgentConfig, EvalCase, ExperimentConfig
        effective_run_id = run_id or f"experiment-{uuid.uuid4().hex}"
        if not cases:
            return fail("cases must not be empty")
        eval_cases = [
            EvalCase(id=case.get("id", f"case-{index}"), name=case.get("name", f"case-{index}"), input=case.get("input", {}), expected=case.get("expected_output"), expected_trajectory=case.get("expected_trajectory"), metadata=case.get("metadata", {}))
            for index, case in enumerate(cases)
        ]
        config = ExperimentConfig(cases=eval_cases, evaluator_names=evaluator_names if evaluator_names is not None else ["output"], rubric=rubric, name=experiment_name, run_id=effective_run_id, agent_config=EvalAgentConfig(model_id=model_id, system_prompt=system_prompt, temperature=temperature))
        import time
        started = time.perf_counter()
        try:
            report = get_runtime().run_experiment(config)
        except (RuntimeError, ValueError) as exc:
            return fail(str(exc))
        request = build_run_request(report, effective_run_id, {"model_id": model_id, "system_prompt_snippet": system_prompt[:80]}, "experiment", (time.perf_counter() - started) * 1000)
        return RunExperimentOutput(run_id=effective_run_id, name=report.experiment_name, case_results=report.case_results, summary=report.summary, evaluators_used=report.evaluator_names, record_run_request=request, persistence=_persist(request))

    @mcp.tool()
    @deterministic(input_model=ListRunResultsInput, output_model=RunResultsOutput)
    def evals_list_run_results() -> ToolResult[RunResultsOutput]:
        """List persisted artifact runs, newest first."""
        from ..runtime.adapters.doc_store_reader import list_runs
        runs = list_runs()
        return RunResultsOutput(runs=runs, count=len(runs), latest=runs[0] if runs else None)

    @mcp.tool()
    @deterministic(input_model=GetRunResultInput, output_model=RunResultOutput)
    def evals_get_run_result(run_id: str) -> ToolResult[RunResultOutput]:
        """Get a full persisted artifact by run ID."""
        from ..runtime.adapters.doc_store_reader import get_run
        result = get_run(run_id)
        return RunResultOutput(found=result is not None, result=result)

    @mcp.tool()
    @operational(input_model=GenerateExperimentInput, output_model=GeneratedExperimentOutput)
    def evals_generate_experiment(context: str, task_description: str, num_cases: int = 5, evaluator_name: str = "output") -> ToolResult[GeneratedExperimentOutput]:
        """Generate test cases using Strands ExperimentGenerator."""
        try:
            config = get_runtime().generate_experiment(context, task_description, num_cases, evaluator_name)
        except RuntimeError as exc:
            return fail(str(exc))
        cases = [{"id": case.id, "name": case.name, "input": case.input, "expected": case.expected, "metadata": case.metadata} for case in config.cases]
        return GeneratedExperimentOutput(name=config.name, cases=cases, evaluator_names=config.evaluator_names, case_count=len(cases))
