"""Import integrity checker - verifies all imports can be resolved.

Uses Python's import machinery as the source of truth.
"""

import ast
import importlib.util
import sys
from pathlib import Path
from typing import Any


def _extract_imports(source: str) -> set[str]:
    """Extract top-level module names from Python source using AST.

    Only extracts imports at module level - skips imports inside functions,
    try blocks, or other nested scopes (those are typically optional deps).
    """
    imports: set[str] = set()
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    imports.add(node.module.split(".")[0])
    except SyntaxError:
        pass
    return imports


def _extract_factory_imports(source: str) -> set[str]:
    """Extract full dotted paths for factory.* imports.

    These are internal imports that must resolve to real modules.
    Returns full module paths like 'factory.auth.runtime.runtime'.
    """
    imports: set[str] = set()
    try:
        tree = ast.parse(source)
        for node in tree.body:
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("factory."):
                        imports.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.level == 0:
                    if node.module.startswith("factory."):
                        imports.add(node.module)
    except SyntaxError:
        pass
    return imports


def _can_import(module_name: str) -> bool:
    """Check if a module can be imported without actually importing it."""
    try:
        spec = importlib.util.find_spec(module_name)
        return spec is not None
    except (ModuleNotFoundError, ValueError):
        return False


# Standard library modules to skip
STDLIB_MODULES = {
    "abc", "ast", "asyncio", "base64", "collections", "contextlib",
    "copy", "dataclasses", "datetime", "enum", "functools", "hashlib",
    "importlib", "inspect", "io", "itertools", "json", "logging",
    "math", "os", "pathlib", "pickle", "platform", "random", "re",
    "shutil", "socket", "sqlite3", "string", "subprocess", "sys",
    "tempfile", "threading", "time", "traceback", "typing", "unittest",
    "urllib", "uuid", "warnings", "weakref", "xml", "zipfile",
    "__future__", "typing_extensions", "concurrent", "multiprocessing",
    "http", "html", "email", "secrets", "struct", "textwrap", "operator",
    "numbers", "decimal", "fractions", "statistics", "cmath", "array",
    "bisect", "heapq", "queue", "types", "contextvars", "graphlib",
}

# Optional third-party modules that may not be installed.
# These are legitimate dependencies for specific bricks/bases but are
# not required for the core workspace to function.
OPTIONAL_MODULES = {
    "flet",         # Flet dashboard base + ui flet adapter/renderers
    "flet_charts",  # Native chart controls for flet adapter
}


def check_import_integrity(workspace_root: Path | None = None) -> dict[str, Any]:
    """Verify all imports in brick source files can be resolved.

    Uses Python's import machinery as the source of truth.
    For factory.* imports, validates the full dotted path (not just
    the top-level 'factory' package) to catch broken internal refs.

    Note: Files in runtime/adapters/ directories are skipped as they
    contain optional backend implementations with soft dependencies.
    """
    if workspace_root is None:
        workspace_root = Path.cwd()

    # Temporarily add all brick src/ dirs so find_spec() resolves
    # components/bases that aren't yet installed in the venv.
    added_paths: list[str] = []
    for brick_area in ("components", "bases"):
        area_dir = workspace_root / brick_area
        if not area_dir.is_dir():
            continue
        for child in sorted(area_dir.iterdir()):
            src_dir = child / "src"
            if src_dir.is_dir():
                p = str(src_dir)
                if p not in sys.path:
                    sys.path.insert(0, p)
                    added_paths.append(p)

    # Invalidate finder caches so the 'factory' namespace package
    # picks up the newly added src/ directories.
    importlib.invalidate_caches()

    try:
        return _run_import_scan(workspace_root)
    finally:
        for p in added_paths:
            try:
                sys.path.remove(p)
            except ValueError:
                pass


def _run_import_scan(workspace_root: Path) -> dict[str, Any]:
    """Scan all brick source files and verify imports resolve."""
    unresolved: list[dict[str, str]] = []
    skipped_adapters: list[str] = []
    files_checked = 0
    imports_checked = 0

    source_files: list[Path] = []
    for search_dir in ("components", "bases"):
        source_files.extend(workspace_root.glob(f"{search_dir}/*/src/**/*.py"))

    for py_file in sorted(source_files):
        rel_path = str(py_file.relative_to(workspace_root))
        if "/adapters/" in rel_path:
            skipped_adapters.append(rel_path)
            continue

        try:
            source = py_file.read_text()

            top_imports = _extract_imports(source)
            files_checked += 1

            for imp in top_imports:
                if imp in STDLIB_MODULES or imp in OPTIONAL_MODULES or imp == "factory":
                    continue
                imports_checked += 1
                if not _can_import(imp):
                    unresolved.append({"module": imp, "file": rel_path})

            factory_imports = _extract_factory_imports(source)
            for imp in factory_imports:
                imports_checked += 1
                if not _can_import(imp):
                    unresolved.append({"module": imp, "file": rel_path})
        except Exception:
            pass

    return {
        "check": "import_integrity",
        "passed": len(unresolved) == 0,
        "files_checked": files_checked,
        "imports_checked": imports_checked,
        "adapters_skipped": len(skipped_adapters),
        "unresolved": unresolved[:20] if unresolved else [],
        "total_unresolved": len(unresolved),
    }
