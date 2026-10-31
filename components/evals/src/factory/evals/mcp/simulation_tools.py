"""Native MCP v2 tools for Strands ActorSimulator multi-turn simulation."""
from __future__ import annotations

import time
import uuid
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational

from ..runtime.run_artifacts import build_run_artifacts
from .simulation_contracts import SimulationInput, SimulationOutput

if TYPE_CHECKING:
    from ..runtime.runtime import EvalsRuntime


def _target(agent_id: str | None, model_id: str) -> dict[str, Any]:
    return {"kind": "registered_persona", "agent_id": agent_id} if agent_id else {
        "kind": "prompt_only", "model_id": model_id,
    }


def _record_request(
    report: Any, run_id: str, agent_id: str | None, model_id: str, duration_ms: float,
) -> dict[str, Any]:
    """Build the complete canonical UPSERT request for durable retry."""
    from ..runtime.run_record_contract import build_run_request
    return build_run_request(
        report, run_id, _target(agent_id, model_id), "simulation", duration_ms,
        artifacts=build_run_artifacts(report),
    )


def _persist_request(request: dict[str, Any], invoker: Callable[..., Any] | None = None) -> dict[str, Any]:
    """Use only the canonical evals_record_run UPSERT for persistence."""
    if invoker is None:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
    if invoker is None:
        return {"requested": True, "persisted": False, "reason": "no tool_invoker"}
    try:
        result = invoker("evals_record_run", **request)
    except Exception as exc:  # noqa: BLE001 — caller receives its retry request
        return {"requested": True, "persisted": False, "reason": str(exc)}
    envelope = result if isinstance(result, ToolResult) else ToolResult.model_validate(result)
    if not envelope.ok or envelope.data is None:
        return {"requested": True, "persisted": False, "reason": envelope.error or "record_run_failed"}
    data = envelope.data.model_dump() if hasattr(envelope.data, "model_dump") else envelope.data
    if not isinstance(data, dict):
        return {"requested": True, "persisted": False, "reason": "invalid record_run data"}
    return {"requested": True, **data}


def _failure(error: str) -> ToolResult[SimulationOutput]:
    return ToolResult(ok=False, data=None, error=error)


def register(mcp: Any, get_runtime: Callable[[], "EvalsRuntime"]) -> None:
    """Register simulation tools."""

    @mcp.tool()
    @operational(input_model=SimulationInput, output_model=SimulationOutput)
    def evals_run_simulation(
        cases: list[dict[str, Any]], evaluator_names: list[str] | None = None,
        rubric: str = "", model_id: str = "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        system_prompt: str = "You are a helpful assistant.", temperature: float = 0.1,
        max_turns: int = 10, experiment_name: str = "simulation",
        agent_id: str | None = None, persist: bool = False, run_id: str | None = None,
        persist_only: bool = False, record_run_request: dict[str, Any] | None = None,
    ) -> ToolResult[SimulationOutput]:
        """Run a simulation or retry its supplied canonical persistence request."""
        if persist_only:
            if not run_id or not record_run_request:
                return _failure("persist_only requires run_id and record_run_request")
            if record_run_request.get("run_id") != run_id:
                return _failure("record_run_request run_id mismatch")
            return SimulationOutput(
                run_id=run_id, persistence=_persist_request(record_run_request),
                record_run_request=record_run_request,
            )
        from ..runtime.ports import EvalAgentConfig, EvalCase, ExperimentConfig
        effective_run_id = run_id or f"simulation-{uuid.uuid4().hex}"
        eval_cases = [
            EvalCase(
                id=case.get("id", f"case-{index}"), name=case.get("name", f"case-{index}"),
                input=case.get("input", ""), expected=case.get("expected_output"),
                metadata=case.get("metadata", {}),
            )
            for index, case in enumerate(cases)
        ]
        config = ExperimentConfig(
            cases=eval_cases, evaluator_names=evaluator_names or ["helpfulness", "goal_success"],
            agent_config=EvalAgentConfig(
                model_id=model_id, system_prompt=system_prompt, temperature=temperature, agent_id=agent_id,
            ),
            rubric=rubric, name=experiment_name, run_id=effective_run_id,
        )
        started = time.perf_counter()
        try:
            report = get_runtime().run_simulation(config, max_turns)
        except Exception as exc:  # noqa: BLE001 — stable id survives all execution failures
            return _failure(f"run_id={effective_run_id}: {exc}")
        result: dict[str, Any] = {
            "run_id": effective_run_id, "name": report.experiment_name,
            "case_results": report.case_results, "summary": report.summary,
            "evaluators_used": report.evaluator_names, "target": _target(agent_id, model_id),
        }
        if persist:
            request = _record_request(
                report, effective_run_id, agent_id, model_id, (time.perf_counter() - started) * 1000,
            )
            result["record_run_request"] = request
            result["persistence"] = _persist_request(request)
        return SimulationOutput(**result)
