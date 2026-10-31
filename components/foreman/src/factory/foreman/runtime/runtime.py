"""Foreman runtime - implements workspace operations.

Provides the default implementation of workspace introspection,
brick scaffolding, and compliance checking.
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from .ports import (
    BrickInfo,
    ComplianceReport,
    ComplianceViolation,
)
from ..core import build_bricks_index, write_bricks_index
from ..guardian import (
    check_branch_naming,
    check_file_sizes,
    check_bricks_index,
    run_all_checks,
)
from ..import_check import check_import_integrity


class ForemanRuntime:
    """Runtime for foreman workspace operations."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self._workspace_root = workspace_root or Path.cwd()

    @property
    def workspace_root(self) -> Path:
        return self._workspace_root

    # WorkspaceIntrospector implementation
    def get_info(self) -> dict[str, Any]:
        """Get workspace overview via poly info."""
        try:
            result = subprocess.run(
                ["uv", "run", "poly", "info"],
                capture_output=True,
                text=True,
                check=False,
                cwd=self._workspace_root,
            )
            return {
                "success": result.returncode == 0,
                "stdout": result.stdout,
                "stderr": result.stderr if result.stderr else None,
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def check_integrity(self) -> dict[str, Any]:
        """Check import integrity across all brick source files."""
        return check_import_integrity(self._workspace_root)

    def list_bricks(self) -> list[BrickInfo]:
        """List all bricks in the workspace."""
        index = build_bricks_index(self._workspace_root)
        bricks: list[BrickInfo] = []

        for comp in index["bricks"]["components"]:
            bricks.append(BrickInfo(
                name=comp["name"],
                brick_type="component",
                namespace=comp.get("namespace", f"factory.{comp['name']}"),
                description=comp.get("description", ""),
                mcp_enabled=comp.get("mcp_enabled", False),
                features=comp.get("features", []),
                path=self._workspace_root / "components" / comp["name"],
            ))

        for base in index["bricks"]["bases"]:
            bricks.append(BrickInfo(
                name=base["name"],
                brick_type="base",
                namespace=base.get("namespace", f"factory.{base['name']}"),
                description=base.get("description", ""),
                mcp_enabled=base.get("mcp_enabled", False),
                features=base.get("features", []),
                path=self._workspace_root / "bases" / base["name"],
            ))

        return bricks

    def get_brick(self, name: str) -> BrickInfo | None:
        """Get information about a specific brick."""
        for brick in self.list_bricks():
            if brick.name == name:
                return brick
        return None

    def build_index(self) -> dict[str, Any]:
        """Build the BRICKS_INDEX from all BRICK.yaml files."""
        return build_bricks_index(self._workspace_root)

    def write_index(self, output_path: Path | None = None) -> dict[str, Any]:
        """Write BRICKS_INDEX.yaml to workspace."""
        return write_bricks_index(
            workspace_root=self._workspace_root,
            output_path=output_path,
        )

    # BrickScaffolder implementation
    def create_component(self, name: str) -> Path:
        """Create a new component using polylith CLI."""
        subprocess.run(
            ["uv", "run", "poly", "create", "component", f"name:{name}"],
            check=True,
            cwd=self._workspace_root,
        )
        return self._workspace_root / "components" / name

    def create_base(self, name: str) -> Path:
        """Create a new base using polylith CLI."""
        subprocess.run(
            ["uv", "run", "poly", "create", "base", f"name:{name}"],
            check=True,
            cwd=self._workspace_root,
        )
        return self._workspace_root / "bases" / name

    # ComplianceChecker implementation
    def check_all(
        self,
        max_lines: int = 200,
        file_size_mode: str = "strict",
        base_sha: str | None = None,
    ) -> ComplianceReport:
        """Run all compliance checks with strict defaults or PR ratcheting."""
        result = run_all_checks(
            self._workspace_root, max_lines, file_size_mode, base_sha
        )

        violations: list[ComplianceViolation] = []
        for check in result["checks"]:
            if not check.get("passed", False):
                if check["check"] == "file_sizes":
                    for v in check.get("violations", []):
                        violations.append(ComplianceViolation(
                            check="file_sizes",
                            message=f"File exceeds {max_lines} LOC",
                            file=v["file"],
                            line_count=v["lines"],
                        ))
                else:
                    violations.append(ComplianceViolation(
                        check=check["check"],
                        message=check.get("error", "Check failed"),
                    ))

        return ComplianceReport(
            passed=result["passed"],
            violations=violations,
            checks_run=[c["check"] for c in result["checks"]],
            summary=result["summary"],
        )

    def check_imports(self) -> dict[str, Any]:
        return check_import_integrity(self._workspace_root)

    def check_branch(self) -> dict[str, Any]:
        return check_branch_naming(self._workspace_root)

    def check_loc(
        self,
        max_lines: int = 200,
        mode: str = "strict",
        base_sha: str | None = None,
    ) -> dict[str, Any]:
        return check_file_sizes(self._workspace_root, max_lines, mode, base_sha)

    def check_index(self) -> dict[str, Any]:
        return check_bricks_index(self._workspace_root)


# Global runtime instance
_runtime: ForemanRuntime | None = None


def get_runtime(workspace_root: Path | None = None) -> ForemanRuntime:
    """Get or create the global ForemanRuntime instance."""
    global _runtime
    if _runtime is None:
        _runtime = ForemanRuntime(workspace_root)
    return _runtime


def reset_runtime() -> None:
    """Reset the global runtime (for testing)."""
    global _runtime
    _runtime = None
