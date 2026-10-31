"""CI guard: every ``factory.<x>`` import in the base must be declared in BRICK.yaml.

This is the sole enforcement mechanism for the ``declared-bricks`` list — see
openspec/changes/add-openarcade-base/tasks.md task 5.3. It walks the base's
source via ``ast``, collects every ``factory.<x>`` import target, and fails
the build with the offending brick name if any target is missing from
``BRICK.yaml``'s ``declared-bricks`` list.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
import yaml

BASE_ROOT = Path(__file__).resolve().parents[3]
SRC_ROOT = BASE_ROOT / "src" / "factory" / "openarcade"
BRICK_YAML = BASE_ROOT / "BRICK.yaml"
SELF_NAMESPACE = "factory.openarcade"


def _collect_factory_imports() -> set[str]:
    """Walk the base's src tree and return every distinct ``factory.<x>`` import."""
    targets: set[str] = set()
    for py in SRC_ROOT.rglob("*.py"):
        tree = ast.parse(py.read_text(encoding="utf-8"), filename=str(py))
        for node in ast.walk(tree):
            module: str | None = None
            if isinstance(node, ast.ImportFrom) and node.module:
                module = node.module
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("factory."):
                        targets.add(alias.name.split(".", 1)[1].split(".")[0])
                continue
            if module and module.startswith("factory."):
                targets.add(module.split(".", 1)[1].split(".")[0])
    targets.discard(SELF_NAMESPACE.split(".", 1)[1])
    return targets


def test_no_undeclared_brick_imports() -> None:
    data = yaml.safe_load(BRICK_YAML.read_text(encoding="utf-8"))
    declared = set(data.get("declared-bricks", []))
    imported = _collect_factory_imports()
    undeclared = sorted(imported - declared)
    assert not undeclared, (
        "Undeclared brick imports in bases/openarcade/src/ — add to "
        f"BRICK.yaml declared-bricks list: {undeclared}"
    )


def test_declared_bricks_list_is_nonempty() -> None:
    data = yaml.safe_load(BRICK_YAML.read_text(encoding="utf-8"))
    assert data.get("declared-bricks"), "BRICK.yaml must declare at least one brick"
