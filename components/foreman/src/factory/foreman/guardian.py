"""Guardian governance and compliance checks for the Python Factory."""

from pathlib import Path
from typing import Any

from .branch_check import check_branch_naming
from .core import build_bricks_index
from .import_check import check_import_integrity
from .loc_check import check_file_sizes
from .mcp_contract_check import check_mcp_contracts
from .project_base_check import check_projects_have_base


def check_bricks_index(workspace_root: Path | None = None) -> dict[str, Any]:
    """Validate BRICKS_INDEX.yaml exists and brick metadata is valid."""
    root = workspace_root or Path.cwd()
    if not (root / "BRICKS_INDEX.yaml").exists():
        return {"check": "bricks_index", "passed": False, "error": "BRICKS_INDEX.yaml not found"}

    fresh_index = build_bricks_index(root)
    errors = []
    if fresh_index.get("missing_metadata"):
        errors.append(f"Missing BRICK.yaml: {fresh_index['missing_metadata']}")
    if fresh_index.get("invalid_metadata"):
        errors.append(f"Invalid BRICK.yaml: {fresh_index['invalid_metadata']}")
    return {
        "check": "bricks_index",
        "passed": not errors,
        "components": len(fresh_index["bricks"]["components"]),
        "bases": len(fresh_index["bricks"]["bases"]),
        "errors": errors or None,
    }


def run_all_checks(
    workspace_root: Path | None = None,
    max_lines: int = 200,
    file_size_mode: str = "strict",
    base_sha: str | None = None,
) -> dict[str, Any]:
    """Run Guardian checks; strict whole-tree governance remains the default."""
    root = workspace_root or Path.cwd()
    checks = [
        check_import_integrity(root),
        check_branch_naming(root),
        check_file_sizes(root, max_lines, mode=file_size_mode, base_sha=base_sha),
        check_bricks_index(root),
        check_projects_have_base(root, mode=file_size_mode, base_sha=base_sha),
        check_mcp_contracts(root, base_sha=base_sha),
    ]
    all_passed = all(check.get("passed", False) for check in checks)
    return {
        "passed": all_passed,
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": sum(1 for check in checks if check.get("passed")),
            "failed": sum(1 for check in checks if not check.get("passed")),
        },
    }


__all__ = [
    "check_branch_naming", "check_bricks_index", "check_file_sizes",
    "check_mcp_contracts", "check_projects_have_base", "run_all_checks",
]
