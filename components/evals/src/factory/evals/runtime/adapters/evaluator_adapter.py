"""Framework-neutral direct evaluator invocation over the provider rail.

The judging framework is selected by name. The provider owns which evaluator
aliases it supports (unknown names raise in ``build``) and whether it can
score the given evidence (insufficient evidence abstains in ``evaluate``), so
this adapter no longer gates on evaluator level.
"""
from __future__ import annotations

import logging
from typing import Any

from .evaluator_factory import EvaluationData
from .evaluator_providers import get_provider
from .evaluator_results import aggregate_rows, run_evaluators

logger = logging.getLogger(__name__)


def _data(input_text: str, output_text: str, expected_output: str | None) -> EvaluationData:
    return EvaluationData(input_text, output_text, expected_output)


def evaluate_output(
    input_text: str,
    output_text: str,
    evaluator_name: str = "non_empty",
    rubric: str = "",
    expected_output: str | None = None,
    framework: str = "deterministic",
) -> dict:
    names = [evaluator_name]
    provider = get_provider(framework)
    rows = run_evaluators(
        provider.build(names, rubric), names,
        _data(input_text, output_text, expected_output), logger,
    )
    return rows[0]


def evaluate_output_multi(
    input_text: str,
    output_text: str,
    evaluator_names: list[str],
    rubric: str = "",
    expected_output: str | None = None,
    framework: str = "deterministic",
    actual_trajectory: list[Any] | None = None,
    expected_trajectory: list[Any] | None = None,
    options: dict[str, Any] | None = None,
) -> dict:
    names = list(evaluator_names)
    provider = get_provider(framework)
    data = EvaluationData(
        input=input_text,
        actual_output=output_text,
        expected_output=expected_output,
        actual_trajectory=actual_trajectory,
        expected_trajectory=expected_trajectory,
    )
    rows = run_evaluators(
        provider.build(names, rubric, options), names, data, logger,
    )
    return aggregate_rows(rows)
