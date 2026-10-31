"""Typed canonical immutable persistence tool for completed Evals runs."""
from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from factory.mcp_utils.interface import (
    JsonArray, JsonObject, ToolResult, get_service, operational,
    validate_protected_persistence,
)

from .contracts.durable import RecordRunInput, RecordRunOutput
from ..runtime.run_record_contract import build_record, document_id, projection_key, record_pointer, utc_timestamp
from ..runtime.run_record_validation import validate_evaluation_run
from ..runtime.edge_model_evidence import EdgeModelEvidence, validation_reason
from ..runtime.trajectory_writer import best_effort_record, default_landing_root


def _storage_payload(result: object) -> object | None:
    """Return a successful Storage DTO payload or a legacy fake dictionary."""
    if isinstance(result, ToolResult):
        return result.data if result.ok else None
    if not isinstance(result, dict) or result.get("ok") is False:
        return None
    return result.get("data") if result.get("ok") is True else result


def register(mcp: Any) -> None:
    """Register the sole durable Evals record writer."""

    @mcp.tool()
    @operational(input_model=RecordRunInput, output_model=RecordRunOutput)
    def evals_record_run(run_id: str, experiment_name: str, verdict: str, pass_rate: float, avg_score: float, total_cases: int, passed: int, case_results: JsonArray | None = None, evaluators_used: JsonArray | None = None, agent: JsonObject | None = None, timestamp: str = "", source: str = "experiment", failed_cases: int | None = None, duration_ms: float = 0.0, case_scores: JsonArray | None = None, summary: JsonObject | None = None, artifacts: JsonObject | None = None, record_kind: str = "evaluation_run", terminal_state: str = "completed", score_projection: JsonObject | None = None, policy_ref: JsonObject | None = None, reviewer_tool_scope: JsonArray | None = None, rubric_digest: str | None = None, attempt_id: str = "") -> ToolResult[RecordRunOutput]:
        """Create an immutable terminal record, match a retry, or report conflict."""
        invoker = get_service("tool_invoker")
        if invoker is None:
            return RecordRunOutput(persisted=False, reason="no tool_invoker", run_id=run_id)
        payload = {"experiment_name": experiment_name, "verdict": verdict, "source": source, "pass_rate": pass_rate, "avg_score": avg_score, "total_cases": total_cases, "passed_cases": passed, "failed_cases": total_cases - passed if failed_cases is None else failed_cases, "duration_ms": round(duration_ms, 1), "evaluators_used": evaluators_used or [], "case_results": case_results or [], "case_scores": case_scores or [], "agent": agent or {}, "summary": summary or {}}
        if artifacts is not None:
            payload["artifacts"] = artifacts
        if score_projection is not None:
            payload.update(score_projection)
        if policy_ref is not None:
            payload["policy_ref"] = policy_ref
        if reviewer_tool_scope is not None:
            payload["reviewer_tool_scope"] = reviewer_tool_scope
        if rubric_digest is not None:
            payload["rubric_digest"] = rubric_digest
        artifact_payload = payload.get("artifacts")
        if isinstance(artifact_payload, dict) and "edge_model_evidence" in artifact_payload:
            try:
                evidence = EdgeModelEvidence.model_validate(
                    artifact_payload["edge_model_evidence"]
                )
            except ValidationError as exc:
                return RecordRunOutput(
                    persisted=False,
                    reason=f"invalid edge_model_evidence: {validation_reason(exc)}",
                    run_id=run_id,
                )
            payload["artifacts"] = {
                **artifact_payload,
                "edge_model_evidence": evidence.model_dump(mode="json"),
            }
        try:
            validate_protected_persistence(payload)
        except ValueError:
            return RecordRunOutput(
                persisted=False,
                reason="protected inline content is forbidden",
                run_id=run_id,
            )
        if record_kind == "evaluation_run":
            reason = validate_evaluation_run(payload)
            if reason:
                return RecordRunOutput(persisted=False, reason=f"invalid evaluation_run: {reason}", run_id=run_id)
        doc_id, requested_timestamp = document_id(run_id, record_kind), timestamp
        try:
            _, record = build_record(run_id=run_id, record_kind=record_kind, terminal_state=terminal_state, payload=payload, timestamp=timestamp or utc_timestamp())
        except (TypeError, ValueError) as exc:
            return RecordRunOutput(persisted=False, reason=f"invalid durable JSON: {exc}", run_id=run_id)

        def commit(current: dict[str, Any]) -> Any:
            return invoker("storage_doc_create_or_match", collection="eval_results", doc_id=doc_id, data=current, content_hash=current["content_hash"])

        try:
            result = commit(record)
            payload_result = _storage_payload(result)
            status = str(
                payload_result.get("status", "failed")
                if isinstance(payload_result, dict)
                else getattr(payload_result, "status", "failed")
            )
            if status == "conflict" and not requested_timestamp:
                existing = _storage_payload(invoker("storage_doc_get", collection="eval_results", doc_id=doc_id))
                data = existing.get("data", existing) if isinstance(existing, dict) else getattr(existing, "data", None)
                if isinstance(data, dict) and "timestamp" in data:
                    _, record = build_record(run_id=run_id, record_kind=record_kind, terminal_state=terminal_state, payload=payload, timestamp=data["timestamp"])
                    result = commit(record)
                    payload_result = _storage_payload(result)
                    status = str(
                        payload_result.get("status", "failed")
                        if isinstance(payload_result, dict)
                        else getattr(payload_result, "status", "failed")
                    )
        except Exception as exc:
            return RecordRunOutput(persisted=False, reason=str(exc), run_id=run_id)
        persisted = status in {"created", "matched"}
        response = RecordRunOutput(
            persisted=persisted,
            status=status,
            doc_id=doc_id,
            run_id=run_id,
            content_hash=record["content_hash"],
            existing_content_hash=str(
                payload_result.get("existing_content_hash", "")
                if isinstance(payload_result, dict)
                else getattr(payload_result, "existing_content_hash", "")
            ),
            timestamp=record["timestamp"],
        )
        if persisted:
            pointer = record_pointer(doc_id, record)
            response = response.model_copy(update={"pointer": pointer, "projection_key": projection_key(pointer)})
            best_effort_record(default_landing_root(), pointer, run_id=run_id, attempt_id=attempt_id, recorded_at=record["timestamp"], verdict=verdict)
        return response
