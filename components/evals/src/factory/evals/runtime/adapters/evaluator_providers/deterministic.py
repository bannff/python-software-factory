"""Honest deterministic evaluator provider — no LLM, no SDK, no lies.

Two evaluators only. ``exact_match`` abstains honestly when it lacks an
expected output rather than pretending a non-empty answer passed; it never
claims to judge helpfulness, coherence, or any other LLM-judge quality.
"""
from __future__ import annotations

from typing import Any

from ..evaluator_factory import EvaluationData, EvaluationOutput

_AVAILABLE = ("exact_match", "non_empty")


class _ExactMatch:
    name = "exact_match"

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        if data.expected_output is None:
            return [EvaluationOutput(
                0.0, False,
                "exact_match requires expected_output; abstained", "abstain",
            )]
        passed = data.actual_output.strip() == data.expected_output.strip()
        reason = (
            "actual_output matched expected_output" if passed
            else "actual_output did not match expected_output"
        )
        return [EvaluationOutput(float(passed), passed, reason, "pass" if passed else "fail")]


class _NonEmpty:
    name = "non_empty"

    def evaluate(self, data: EvaluationData) -> list[EvaluationOutput]:
        passed = bool(data.actual_output.strip())
        reason = "non-empty output" if passed else "empty output"
        return [EvaluationOutput(float(passed), passed, reason, "pass" if passed else "fail")]


_BUILDERS = {"exact_match": _ExactMatch, "non_empty": _NonEmpty}


class DeterministicProvider:
    """Framework-neutral deterministic provider (``framework="deterministic"``)."""

    framework = "deterministic"

    def available(self) -> list[str]:
        return list(_AVAILABLE)

    def build(
        self, names: list[str], rubric: str = "",
        options: dict[str, Any] | None = None,
    ) -> list:
        del rubric, options  # deterministic evaluators take no rubric/options
        unknown = sorted({name for name in names if name not in _BUILDERS})
        if unknown:
            raise ValueError(
                f"deterministic provider does not support: {', '.join(unknown)}. "
                f"available: {', '.join(_AVAILABLE)}"
            )
        return [_BUILDERS[name]() for name in names]
