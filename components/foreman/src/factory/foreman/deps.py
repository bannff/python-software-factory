"""Brick dependency resolver — declared metadata plus deep AST scanning.

Declared BRICK.yaml dependencies preserve MCP-only edges that intentionally
have no Python import. AST scanning remains the source for discovered edges.
"""

import ast
from pathlib import Path
from typing import Any

from .brick_metadata import (
    find_brick_yaml as _find_brick_yaml,
    read_brick_dependencies,
    read_brick_pip_packages,
)
from .deps_map import IMPORT_TO_PACKAGE, STDLIB as _STDLIB


def _scan_brick_imports(brick_src: Path) -> tuple[set[str], set[str]]:
    """Deep-scan a brick for factory and third-party imports (ast.walk)."""
    factory_bricks: set[str] = set()
    third_party: set[str] = set()
    for py_file in brick_src.rglob("*.py"):
        if "__pycache__" in str(py_file):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if alias.name.startswith("factory."):
                        parts = alias.name.split(".")
                        if len(parts) >= 2:
                            factory_bricks.add(parts[1])
                    elif top not in _STDLIB:
                        third_party.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    if node.module.startswith("factory."):
                        parts = node.module.split(".")
                        if len(parts) >= 2:
                            factory_bricks.add(parts[1])
                    elif top not in _STDLIB:
                        third_party.add(top)
    return factory_bricks, third_party


def _scan_adapter_imports(brick_src: Path, adapter_names: list[str]) -> set[str]:
    """Scan adapter files matching adapter_names for third-party imports."""
    third_party: set[str] = set()
    adapters_dir = brick_src / "runtime" / "adapters"
    if not adapters_dir.exists():
        return third_party
    for py_file in adapters_dir.glob("*.py"):
        stem = py_file.stem
        if not any(stem.startswith(n) or n in stem for n in adapter_names):
            continue
        try:
            tree = ast.parse(py_file.read_text())
        except (SyntaxError, OSError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    top = alias.name.split(".")[0]
                    if top not in _STDLIB and not alias.name.startswith("factory."):
                        third_party.add(top)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    top = node.module.split(".")[0]
                    if top not in _STDLIB and not node.module.startswith("factory."):
                        third_party.add(top)
            elif isinstance(node, ast.Call):
                # Catch __import__("pkg") and _check_import("pkg") style calls
                func_name = None
                if isinstance(node.func, ast.Name):
                    func_name = node.func.id
                elif isinstance(node.func, ast.Attribute):
                    func_name = node.func.attr
                if (func_name and "import" in func_name.lower()
                        and node.args and isinstance(node.args[0], ast.Constant)
                        and isinstance(node.args[0].value, str)):
                    top = node.args[0].value.split(".")[0]
                    if top not in _STDLIB and not node.args[0].value.startswith("factory."):
                        third_party.add(top)
    return third_party


def _find_brick_src(name: str, workspace_root: Path) -> Path | None:
    """Locate the source directory for a brick by name."""
    for prefix in ("components", "bases"):
        candidate = workspace_root / prefix / name / "src" / "factory" / name
        if candidate.exists():
            return candidate
    return None


def resolve_dependencies(
    bricks: list[str],
    workspace_root: Path | None = None,
    include_adapters: list[str] | None = None,
) -> dict[str, Any]:
    """Resolve transitive brick deps.  Uses BRICK.yaml pip_packages when
    available, falls back to deep AST scanning otherwise."""
    if workspace_root is None:
        workspace_root = Path.cwd()
    requested = set(bricks)
    resolved: set[str] = set()
    all_third_party: set[str] = set()
    cached_packages: set[str] = set()
    queue = list(requested)
    not_found: list[str] = []
    used_cache = False

    while queue:
        name = queue.pop(0)
        if name in resolved:
            continue
        resolved.add(name)
        src = _find_brick_src(name, workspace_root)
        if src is None:
            not_found.append(name)
            continue
        cached = read_brick_pip_packages(name, workspace_root)
        if cached is not None:
            cached_packages.update(cached)
            used_cache = True
            factory_deps, _ = _scan_brick_imports(src)
        else:
            factory_deps, third_party = _scan_brick_imports(src)
            all_third_party.update(third_party)
        factory_deps.update(read_brick_dependencies(name, workspace_root))
        for dep in factory_deps:
            if dep not in resolved and dep != name:
                queue.append(dep)

    required = resolved - requested - set(not_found)
    adapter_third_party: set[str] = set()
    if include_adapters:
        for name in resolved - set(not_found):
            src = _find_brick_src(name, workspace_root)
            if src:
                adapter_third_party.update(
                    _scan_adapter_imports(src, include_adapters)
                )
    all_third_party.update(adapter_third_party)
    scanned_packages: set[str] = {
        IMPORT_TO_PACKAGE[imp] for imp in all_third_party if imp in IMPORT_TO_PACKAGE
    }
    packages: list[str] = sorted(scanned_packages | cached_packages)
    return {
        "requested": sorted(requested),
        "required": sorted(required),
        "resolved": sorted(resolved - set(not_found)),
        "not_found": not_found,
        "python_packages": packages,
        "adapter_imports": sorted(adapter_third_party) if include_adapters else [],
        "used_cache": used_cache,
    }
