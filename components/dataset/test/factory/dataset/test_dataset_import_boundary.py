"""Import-boundary guard for the dataset brick.

Split from test_stage_adapters.py (LOC tenet). This canary prevents Dataset
from importing Agent, Strands, or retired upstream agentic_datasets/litellm
packages; legacy LLM adapter source remains isolated from the default registry.
"""

from __future__ import annotations

import ast
from pathlib import Path


def test_dataset_brick_does_not_import_agent_strands_or_upstream() -> None:
    """Guard Dataset against Agent and retired upstream imports."""
    dataset_src = Path(__file__).resolve().parents[3] / "src" / "factory" / "dataset"
    forbidden = (
        "factory.agent", "strands", "agentic_datasets", "litellm",
    )
    failures = []
    for path in dataset_src.rglob("*.py"):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith(forbidden):
                        failures.append(f"{path}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if module.startswith(forbidden):
                    failures.append(f"{path}: from {module}")
    assert not failures, "dataset brick imports forbidden modules: " + "; ".join(failures)


def test_can_terminal_does_not_import_machine_learning() -> None:
    """The Dataset-owned terminal must stop at immutable wire artifacts."""
    dataset_src = Path(__file__).resolve().parents[3] / "src" / "factory" / "dataset"
    paths = [
        *dataset_src.joinpath("runtime").glob("can_terminal*.py"),
        dataset_src / "mcp" / "can_terminal.py",
    ]
    failures = []
    for path in paths:
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            module = node.module if isinstance(node, ast.ImportFrom) else None
            names = [alias.name for alias in node.names] if isinstance(
                node, (ast.Import, ast.ImportFrom)
            ) else []
            if (module or "").startswith("factory.machine_learning") or any(
                name.startswith("factory.machine_learning") for name in names
            ):
                failures.append(str(path))
    assert not failures, "CAN terminal imports machine_learning: " + "; ".join(failures)
