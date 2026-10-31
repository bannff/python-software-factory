"""Shared EvalCase → Strands Case conversion.

Single source of truth for converting the evals brick's port type
(EvalCase) to the Strands SDK's Case[str, str]. Used by both
experiment_runner.py and simulator_adapter.py.
"""
from __future__ import annotations

from typing import Any

from ..ports import EvalCase


def cases_to_strands(cases: list[EvalCase]) -> list[Any]:
    """Convert EvalCase list to Strands Case[str, str] list."""
    from strands_evals import Case
    result = []
    for c in cases:
        raw = c.input
        input_str = (
            raw if isinstance(raw, str)
            else raw.get("query", raw.get("input", str(raw)))
        )
        kwargs: dict[str, Any] = {
            "name": c.name or c.id,
            "input": input_str,
            "metadata": c.metadata,
        }
        if c.expected:
            if isinstance(c.expected, str):
                kwargs["expected_output"] = c.expected
            elif isinstance(c.expected, dict):
                kwargs["expected_output"] = c.expected.get(
                    "output", c.expected.get("response", str(c.expected)),
                )
            else:
                kwargs["expected_output"] = str(c.expected)
        if c.expected_trajectory:
            kwargs["expected_trajectory"] = c.expected_trajectory
        result.append(Case[str, str](**kwargs))
    return result
