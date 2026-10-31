"""Fail-closed validation of normalized evaluator evidence."""
from __future__ import annotations

from typing import Any


def validate_session_evidence(session: Any) -> dict[str, Any]:
    """Require a mapping with non-empty traces and spans."""
    if hasattr(session, "model_dump"):
        session = session.model_dump(mode="json")
    if not isinstance(session, dict):
        raise ValueError("session must be normalized evaluation evidence")
    traces = session.get("traces")
    if not isinstance(traces, list) or not any(
        isinstance(trace, dict) and trace.get("spans") for trace in traces
    ):
        raise ValueError("session evidence must contain non-empty traces and spans")
    return session


def validate_evaluator_evidence(
    evaluator_names: list[str], session: Any,
    actual_interactions: list[dict[str, Any]] | None = None,
) -> None:
    from .evaluator_factory import INTERACTIONS_EVALUATORS, validate_evaluator_names

    names = set(validate_evaluator_names(evaluator_names))
    validate_session_evidence(session)
    if names & INTERACTIONS_EVALUATORS:
        _validate_interactions(actual_interactions)


def _validate_interactions(interactions: list[dict[str, Any]] | None) -> None:
    if not isinstance(interactions, list) or not interactions:
        raise ValueError("interactions evaluator requires explicit non-empty actual_interactions")
    for index, interaction in enumerate(interactions):
        if not isinstance(interaction, dict):
            raise ValueError(f"actual_interactions[{index}] must be an object")
        node, dependencies, messages = (
            interaction.get("node_name"), interaction.get("dependencies"),
            interaction.get("messages"),
        )
        if node is not None and not isinstance(node, str):
            raise ValueError(f"actual_interactions[{index}].node_name must be a string")
        if dependencies is not None and not isinstance(dependencies, list):
            raise ValueError(f"actual_interactions[{index}].dependencies must be a list")
        if messages is not None and not isinstance(messages, list):
            raise ValueError(f"actual_interactions[{index}].messages must be a list")
        if not ((isinstance(node, str) and node.strip()) or dependencies or messages):
            raise ValueError(f"actual_interactions[{index}] lacks meaningful evidence")
