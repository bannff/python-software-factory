"""Evaluate normalized session and interaction evidence."""
from __future__ import annotations

import json
import logging
from typing import Any

from .evidence_validation import validate_evaluator_evidence, validate_session_evidence
from .evaluator_factory import EvaluationData, validate_evaluator_names
from .evaluator_providers import get_provider
from .evaluator_results import aggregate_rows, run_evaluators

logger = logging.getLogger(__name__)


def _build_session(
    otel_spans_json: list[str] | None = None,
    session_data: dict[str, Any] | None = None,
    session_id: str = "unknown",
    session: Any | None = None,
) -> dict[str, Any]:
    if session is not None:
        return validate_session_evidence(session)
    if otel_spans_json is not None:
        if not otel_spans_json:
            raise ValueError("otel_spans_json must contain at least one span")
        spans = []
        for raw in otel_spans_json:
            try:
                value = json.loads(raw) if isinstance(raw, str) else raw
            except (TypeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid OTEL span JSON: {exc}") from exc
            if isinstance(value, dict):
                spans.append(value)
        return validate_session_evidence({
            "session_id": session_id,
            "traces": [{"trace_id": session_id, "spans": spans}],
        })
    if session_data is not None:
        return validate_session_evidence(session_data)
    raise ValueError("session, non-empty otel_spans_json, or non-empty session_data is required")


def evaluate_with_real_session(
    input_text: str,
    output_text: str,
    evaluator_names: list[str],
    session_data: dict[str, Any] | None = None,
    rubric: str = "",
    expected_output: str | None = None,
    otel_spans_json: list[str] | None = None,
    session: Any | None = None,
    actual_interactions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    names = list(validate_evaluator_names(evaluator_names))
    sid = session_data.get("session_id", "unknown") if session_data else "unknown"
    resolved = _build_session(otel_spans_json, session_data, sid, session)
    validate_evaluator_evidence(names, resolved, actual_interactions)
    data = EvaluationData(
        input=input_text, actual_output=output_text,
        expected_output=expected_output, actual_trajectory=resolved,
        actual_interactions=actual_interactions,
    )
    evaluators = get_provider("strands").build(names, rubric)
    rows = run_evaluators(evaluators, names, data, logger)
    return aggregate_rows(rows, all_supported=True)
