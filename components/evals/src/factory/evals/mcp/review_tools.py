"""Typed Evals review acceptance and immutable recording tool."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, fail, get_service, operational
from factory.mcp_utils.registration import typed_tool

from ..runtime.review_record import decide_review
from .contracts.durable import RecordRunOutput
from .contracts.review import ReviewAndRecordInput, ReviewAndRecordOutput


def register(mcp: Any) -> None:
    @typed_tool(mcp)
    @operational(input_model=ReviewAndRecordInput, output_model=ReviewAndRecordOutput)
    def evals_review_and_record(
        run_id: str, policy_id: str, manifest_digest: str,
        rows: list[dict[str, Any]], agent: dict[str, Any] | None = None,
    ) -> ToolResult[ReviewAndRecordOutput]:
        decision = decide_review(
            run_id, policy_id, manifest_digest, rows, agent or {},
        )
        invoker = get_service("tool_invoker")
        if not callable(invoker):
            return fail("immutable Evals writer unavailable")
        raw = invoker("evals_record_run", **decision.request)
        record = _record(raw)
        if record is None or not record.persisted:
            return fail(record.reason if record is not None else "review record failed")
        return ReviewAndRecordOutput(
            policy_id=decision.policy_id, verdict=decision.verdict,
            pass_rate=decision.pass_rate, avg_score=decision.avg_score,
            record=record,
        )


def _record(raw: Any) -> RecordRunOutput | None:
    if isinstance(raw, ToolResult):
        return raw.data if raw.ok and isinstance(raw.data, RecordRunOutput) else None
    if isinstance(raw, RecordRunOutput):
        return raw
    if isinstance(raw, dict):
        value = raw.get("data", raw)
        try:
            return RecordRunOutput.model_validate(value)
        except Exception:
            return None
    return None


__all__ = ["register"]
