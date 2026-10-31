"""Workflow-attested dev-loop scoring through existing Learning sources."""
from __future__ import annotations

import hashlib
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, get_service, operational, protected_canonical_json, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.projection import DevLoopScoreOutput, TrustedDevLoopInput
from ..runtime.generic_score_dispatch import handle_generic_score_dispatch
from ..runtime.models import Event

if TYPE_CHECKING:
    from ..runtime.runtime import EventsRuntime


def score_material(values: dict[str, Any]) -> dict[str, Any]:
    return {key: values[key] for key in (
        "loop_id", "cycle_id", "workflow_run_id", "report_digest",
        "input_summary", "output_summary",
    )}


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"]) -> None:
    del get_runtime

    @typed_tool(mcp)
    @service_only(callers={"workflow"}, binding="projection")
    @operational(input_model=TrustedDevLoopInput, output_model=DevLoopScoreOutput)
    def events_score_dev_loop_cycle(
        tenant_id: str, owner_id: str, event_type: str,
        subject_id: str, revision: int, payload_digest: str,
        loop_id: str, cycle_id: str, workflow_run_id: str,
        report_digest: str, input_summary: str, output_summary: str,
    ) -> ToolResult[DevLoopScoreOutput]:
        values = locals()
        expected = hashlib.sha256(protected_canonical_json(
            score_material(values),
        )).hexdigest()
        if payload_digest != expected or subject_id != cycle_id:
            return DevLoopScoreOutput(scored=False, error="cycle_attestation_mismatch")
        invoker = get_service("tool_invoker")
        if not callable(invoker):
            return DevLoopScoreOutput(scored=False, error="learning_unavailable")
        payload = {
            "run_id": workflow_run_id, "workflow_run_id": workflow_run_id,
            "tenant_id": tenant_id, "principal_id": owner_id,
            "loop_id": loop_id, "cycle_id": cycle_id,
            "settlement_revision": revision, "report_digest": report_digest,
            "input_summary": input_summary, "output_summary": output_summary,
            "workflow_type": "dev-loop", "domain_class": "dev-loop",
            "reward_identity": f"{tenant_id}:{owner_id}:{loop_id}:{cycle_id}:{revision}",
        }
        result = handle_generic_score_dispatch(Event(
            source="workflow", type=event_type, payload=payload,
            principal_id=owner_id,
        ), invoker)
        reward = result.get("reward") if isinstance(result, dict) else None
        if not isinstance(reward, dict) or reward.get("deduped") is True:
            return DevLoopScoreOutput(
                scored=bool(isinstance(reward, dict)), reward=reward,
                error=None if isinstance(reward, dict) else "reward_abstained",
            )
        return DevLoopScoreOutput(scored=True, reward=reward)


__all__ = ["register", "score_material"]
