"""ActorSimulator adapter with faithful target and actor evidence."""
from __future__ import annotations

from datetime import datetime, timezone
import logging
import uuid
from typing import Any, Callable

from ..ports import EvalAgentConfig, ExperimentConfig, ExperimentReport
from .case_adapter import cases_to_strands
from ..simulation_report import build_report as _build_report

logger = logging.getLogger(__name__)


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()


def _jsonable(value: Any) -> Any:
    """Snapshot evidence without retaining mutable SDK/session objects."""
    if hasattr(value, "model_dump"):
        return _jsonable(value.model_dump(mode="json"))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value if value is None or isinstance(value, (bool, int, float, str)) else str(value)


def _span_snapshot(spans: tuple[Any, ...]) -> list[dict[str, Any]]:
    return [{
        "name": str(getattr(span, "name", "")),
        "start_time": getattr(span, "start_time", None),
        "end_time": getattr(span, "end_time", None),
        "attributes": _jsonable(dict(getattr(span, "attributes", {}) or {})),
    } for span in spans]


def _take_spans(capture: Any) -> tuple[Any, ...]:
    spans = tuple(capture.get_finished_spans())
    capture.clear()
    return spans


def _persona_response(agent_id: str, thread_id: str, message: str) -> str:
    """Invoke a registered Companion-X persona through the MCP gateway."""
    from factory.mcp_utils.interface import get_service
    invoker = get_service("tool_invoker")
    if invoker is None:
        raise RuntimeError("agent simulation requires the MCP tool_invoker")
    result = invoker(
        "agent_reason", task=message,
        context={"thread_id": thread_id, "simulation_correlation_id": thread_id},
        agent_id=agent_id,
    )
    if not isinstance(result, dict) or result.get("status") != "completed":
        detail = result.get("output", result) if isinstance(result, dict) else result
        raise RuntimeError(f"registered persona {agent_id!r} failed: {detail}")
    return str(result.get("output", ""))


def _run_case(
    simulator: Any, capture: Any, invoke_target: Callable[[str], str], initial_message: str,
    correlation_id: str,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Run one case, never allowing actor spans into target evaluation."""
    capture.clear()
    target_spans: list[Any] = []
    actor_turns: list[dict[str, Any]] = []
    user_message, agent_response, turn = initial_message, "", 0
    while simulator.has_next():
        turn += 1
        target_started = _timestamp()
        agent_response = invoke_target(user_message)
        target_finished = _timestamp()
        target_spans.extend(_take_spans(capture))
        actor_started = _timestamp()
        actor_result = simulator.act(agent_response)
        actor_finished = _timestamp()
        actor = actor_result.structured_output
        actor_turns.append({
            "turn": turn,
            "target_message": user_message,
            "target_response": agent_response,
            "actor": {
                "reasoning": str(getattr(actor, "reasoning", "")),
                "message": _jsonable(getattr(actor, "message", None)),
                "stop": bool(getattr(actor, "stop", False)),
                "stop_reason": getattr(actor, "stop_reason", None),
            },
            "timestamps": {
                "target_started_at": target_started, "target_finished_at": target_finished,
                "actor_started_at": actor_started, "actor_finished_at": actor_finished,
            },
            "actor_span_snapshot": _span_snapshot(_take_spans(capture)),
        })
        user_message = str(getattr(actor, "message", ""))
    target_snapshot = tuple(target_spans)
    session = capture.spans_to_session(list(target_snapshot), session_id=correlation_id)
    return {"output": agent_response, "trajectory": session}, {
        "correlation_id": correlation_id,
        "target_span_snapshot": _span_snapshot(target_snapshot),
        "target_session": _jsonable(session),
        "actor_turns": actor_turns,
    }


def run_simulation(config: ExperimentConfig, max_turns: int = 10) -> ExperimentReport:
    """Run ActorSimulator against a prompt-only or registered-persona target."""
    from strands import Agent
    from strands_evals import ActorSimulator, Case, Experiment
    from factory.telemetry.interface import get_capture
    from .evaluator_factory import build_evaluators
    agent_cfg = config.agent_config or EvalAgentConfig()
    capture = get_capture().setup()
    run_id = config.run_id or uuid.uuid4().hex
    evidence_by_execution: list[dict[str, Any]] = []

    def task_fn(case: Case) -> dict[str, Any]:
        correlation_id = f"simulation-{run_id}-{uuid.uuid4().hex}"
        simulator = ActorSimulator.from_case_for_user_simulator(case=case, max_turns=max_turns)
        if agent_cfg.agent_id:
            invoke_target = lambda message: _persona_response(agent_cfg.agent_id or "", correlation_id, message)
        else:
            target = Agent(
                system_prompt=agent_cfg.system_prompt, model=agent_cfg.model_id, callback_handler=None,
                trace_attributes={"gen_ai.conversation.id": correlation_id, "session.id": correlation_id},
            )
            invoke_target = lambda message: str(target(message))
        result, evidence = _run_case(simulator, capture, invoke_target, str(case.input), correlation_id)
        evidence_by_execution.append(evidence)
        return result
    experiment = Experiment(
        cases=cases_to_strands(config.cases),
        evaluators=build_evaluators(config.evaluator_names, config.rubric, framework="strands"),
    )
    return _build_report(config, experiment.run_evaluations(task_fn), evidence_by_execution)
