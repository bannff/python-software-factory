"""Strands Evals SDK experiment orchestration.

Converts EvalCase/ExperimentConfig to Strands SDK types, runs
experiments via Experiment.run_evaluations, and generates
experiment configs from context.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from ..ports import EvalCase, ExperimentConfig, ExperimentReport
from .evaluator_factory import build_evaluators
from .evaluator_results import json_safe_details
from .agent_task import build_agent_fn
from .case_adapter import cases_to_strands

logger = logging.getLogger(__name__)


def run_strands_experiment(config: ExperimentConfig) -> ExperimentReport:
    """Run a Strands experiment end-to-end."""
    from strands_evals import Experiment
    strands_cases = cases_to_strands(config.cases)
    task_fn = build_agent_fn(config.agent_config, config.evaluator_names)
    evaluators = build_evaluators(config.evaluator_names, config.rubric, framework="strands")
    experiment = Experiment[str, str](cases=strands_cases, evaluators=evaluators)
    report = experiment.run_evaluations(task_fn)
    case_results: list[dict[str, Any]] = []
    rows = zip(
        report.cases,
        report.scores,
        report.test_passes,
        report.reasons,
        report.detailed_results,
        strict=True,
    )
    for index, (case_rec, score, passed, reason, details) in enumerate(rows):
        evaluator = str(case_rec.get("evaluator", ""))
        case_results.append({
            "case_name": case_rec.get("name", f"case-{index}"),
            "evaluator": evaluator,
            "evaluator_type": str(case_rec.get("evaluator_type", "")),
            "evaluator_ordinal": config.evaluator_names.index(evaluator),
            "score": float(score),
            "passed": bool(passed),
            "reason": reason,
            "detailed_results": json_safe_details(details),
        })
    passes = report.test_passes
    summary = {
        "overall_score": report.overall_score,
        "pass_rate": sum(passes) / len(passes) if passes else 0.0,
        "total_cases": len(config.cases),
        "total_evaluation_rows": len(case_results),
    }
    return ExperimentReport(
        experiment_name=config.name or "experiment",
        case_results=case_results,
        summary=summary,
        evaluator_names=config.evaluator_names,
    )


def generate_strands_experiment(
    context: str,
    task_description: str,
    num_cases: int = 5,
    evaluator_name: str = "output",
) -> ExperimentConfig:
    """Generate an experiment config from context using ExperimentGenerator."""
    from strands_evals.generators import ExperimentGenerator
    from .evaluator_factory import get_evaluator_class
    evaluator_cls = get_evaluator_class(evaluator_name, framework="strands")
    generator = ExperimentGenerator[str, str](
        input_type=str, output_type=str, include_expected_output=True,
    )

    async def _generate():
        return await generator.from_context_async(
            context=context, task_description=task_description,
            num_cases=num_cases, evaluator=evaluator_cls,
        )
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None
    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            experiment = pool.submit(asyncio.run, _generate()).result()
    else:
        experiment = asyncio.run(_generate())
    cases = []
    for i, sc in enumerate(experiment.cases):
        cases.append(EvalCase(
            id=f"gen-{i}",
            name=sc.name or f"case-{i}",
            input={"query": sc.input} if isinstance(sc.input, str) else sc.input,
            expected={"output": sc.expected_output} if sc.expected_output else None,
            metadata=sc.metadata or {},
        ))
    return ExperimentConfig(
        cases=cases,
        evaluator_names=[evaluator_name],
        name=f"generated-{task_description[:30]}",
    )
