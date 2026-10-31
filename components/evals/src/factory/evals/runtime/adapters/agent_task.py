"""Build generic Strands agent task functions for experiments."""
from __future__ import annotations

from typing import Any

from ..ports import EvalAgentConfig
from .evaluator_factory import needs_trace, validate_evaluator_names


def build_agent_fn(agent_config: EvalAgentConfig | None, evaluator_names: list[str]):
    """Build a task function backed by one generic Strands Agent per case.

    This path can authoritatively produce output and telemetry Sessions. It
    cannot produce multi-agent interaction evidence, so that evaluator is
    rejected rather than synthesized from telemetry.
    """
    names = list(validate_evaluator_names(evaluator_names))
    if "interactions" in names:
        raise ValueError(
            "interactions evaluator is unsupported for generic agent experiments: "
            "no authoritative actual_interactions producer is available"
        )
    from strands import Agent
    config = agent_config or EvalAgentConfig()
    trace = needs_trace(names)
    capture = None
    if trace:
        from factory.telemetry.interface import get_capture
        capture = get_capture().setup()

    def task_fn(case) -> str | dict[str, Any]:
        if capture:
            capture.clear()
        agent_kwargs: dict[str, Any] = {
            "system_prompt": config.system_prompt,
            "model": config.model_id,
            "callback_handler": None,
        }
        if trace:
            sid = getattr(case, "session_id", None) or case.name
            agent_kwargs["trace_attributes"] = {
                "gen_ai.conversation.id": sid,
                "session.id": sid,
            }
        agent = Agent(**agent_kwargs)
        response = agent(case.input)
        if not capture:
            return str(response)
        spans = capture.get_finished_spans()
        sid = getattr(case, "session_id", None) or case.name
        session = capture.spans_to_session(spans, session_id=sid)
        from .evidence_validation import validate_evaluator_evidence
        validate_evaluator_evidence(names, session)
        return {"output": str(response), "trajectory": session}
    return task_fn
