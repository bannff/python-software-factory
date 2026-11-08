"""Loading and live-refreshing workflow definitions from config_dir."""
from __future__ import annotations

from pathlib import Path

import yaml

from .models import WorkflowDefinition
from .operations import WorkflowError


def load_workflows(config_dir: Path) -> list[WorkflowDefinition]:
    definitions = []
    workflows_dir = config_dir / "workflows"
    if workflows_dir.exists():
        for path in sorted(workflows_dir.glob("*.yaml")):
            parsed = yaml.safe_load(path.read_text())
            if not isinstance(parsed, dict):
                raise WorkflowError(f"Workflow file must parse to a mapping: {path}")
            definitions.append(WorkflowDefinition.model_validate(parsed))
    return definitions


def replace_registry(
    config_dir: Path,
    workflows: list[WorkflowDefinition],
    by_id: dict[str, WorkflowDefinition],
    by_name: dict[str, WorkflowDefinition],
) -> None:
    """Re-read config_dir into the given containers, mutating them in place.

    Runner and WorkflowOperations hold references to the same dicts, so they
    must not be rebound. Loading happens first: a bad file raises before any
    container changes.
    """
    definitions = load_workflows(config_dir)
    workflows[:] = definitions
    by_id.clear()
    by_id.update((w.id, w) for w in definitions)
    by_name.clear()
    by_name.update((w.name.lower(), w) for w in definitions)
