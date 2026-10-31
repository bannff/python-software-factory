"""Experiment serialization adapter using Strands SDK.

Wraps Experiment.to_file/from_file/to_dict/from_dict for
saving and loading experiments through the MCP interface.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from ..ports import EvalCase, ExperimentConfig

logger = logging.getLogger(__name__)

DEFAULT_DIR = ".object_store"


def save_experiment(config: ExperimentConfig, filename: str) -> dict[str, Any]:
    """Save an experiment config to JSON via Strands SDK serialization."""
    from strands_evals import Experiment
    from .evaluator_factory import build_evaluators
    strands_cases = _config_to_cases(config)
    evaluators = build_evaluators(config.evaluator_names, config.rubric, framework="strands")
    experiment = Experiment[str, str](cases=strands_cases, evaluators=evaluators)
    path = _resolve_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    experiment.to_file(str(path))
    return {
        "path": str(path),
        "cases": len(strands_cases),
        "evaluators": config.evaluator_names,
    }


def load_experiment(filename: str) -> ExperimentConfig:
    """Load an experiment from JSON via Strands SDK deserialization."""
    from strands_evals import Experiment
    from .evaluator_factory import alias_for_evaluator, evaluator_classes
    path = _resolve_path(filename)
    experiment = Experiment.from_file(
        str(path), custom_evaluators=evaluator_classes(framework="strands"),
    )
    cases = []
    for i, sc in enumerate(experiment.cases):
        cases.append(EvalCase(
            id=f"loaded-{i}",
            name=getattr(sc, "name", f"case-{i}"),
            input={"query": sc.input} if isinstance(sc.input, str) else sc.input,
            expected=(
                {"output": sc.expected_output} if sc.expected_output else None
            ),
            metadata=getattr(sc, "metadata", {}) or {},
        ))
    evaluator_names = [alias_for_evaluator(evaluator, framework="strands") for evaluator in experiment.evaluators]
    return ExperimentConfig(
        cases=cases,
        evaluator_names=evaluator_names,
        name=path.stem,
    )


def list_saved_experiments() -> list[dict[str, Any]]:
    """List all saved experiment files."""
    base = Path(DEFAULT_DIR)
    if not base.exists():
        return []
    results = []
    for f in sorted(base.glob("*.json")):
        try:
            data = json.loads(f.read_text())
            # Only include files that look like experiment configs (have a 'cases' list)
            if not isinstance(data.get("cases"), list):
                continue
            results.append({
                "filename": f.name,
                "path": str(f),
                "cases": len(data.get("cases", [])),
                "size_bytes": f.stat().st_size,
            })
        except (json.JSONDecodeError, OSError):
            continue
    return results


def _config_to_cases(config: ExperimentConfig) -> list:
    """Convert ExperimentConfig cases to Strands Case list."""
    from strands_evals import Case
    result = []
    for c in config.cases:
        raw = c.input
        input_str = raw if isinstance(raw, str) else raw.get("query", raw.get("input", str(raw)))
        kwargs: dict[str, Any] = {
            "name": c.name or c.id,
            "input": input_str,
            "metadata": c.metadata,
        }
        if c.expected:
            if isinstance(c.expected, str):
                kwargs["expected_output"] = c.expected
            else:
                kwargs["expected_output"] = c.expected.get(
                    "output", c.expected.get("response", str(c.expected)),
                )
        result.append(Case[str, str](**kwargs))
    return result


def _resolve_path(filename: str) -> Path:
    """Resolve filename to a path in the object store."""
    p = Path(filename)
    if not p.suffix:
        p = p.with_suffix(".json")
    if not p.is_absolute() and not str(p).startswith(DEFAULT_DIR):
        p = Path(DEFAULT_DIR) / p
    return p
