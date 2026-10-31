"""Foreman ports - Protocol interfaces for workspace operations.

Defines abstract interfaces for workspace introspection, brick scaffolding,
and compliance checking. Adapters can plug in different implementations.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@dataclass
class BrickInfo:
    """Information about a brick in the workspace."""

    name: str
    brick_type: str  # "component" or "base"
    namespace: str
    description: str = ""
    mcp_enabled: bool = False
    features: list[str] = field(default_factory=list)
    path: Path | None = None


@dataclass
class ComplianceViolation:
    """A single compliance violation."""

    check: str
    message: str
    file: str | None = None
    line_count: int | None = None
    severity: str = "error"  # error, warning, info


@dataclass
class ComplianceReport:
    """Result of compliance checks."""

    passed: bool
    violations: list[ComplianceViolation] = field(default_factory=list)
    checks_run: list[str] = field(default_factory=list)
    summary: dict[str, Any] = field(default_factory=dict)


@runtime_checkable
class WorkspaceIntrospector(Protocol):
    """Port: Workspace introspection operations."""

    def get_info(self) -> dict[str, Any]:
        """Get workspace overview information."""
        ...

    def check_integrity(self) -> dict[str, Any]:
        """Check polylith workspace integrity."""
        ...

    def list_bricks(self) -> list[BrickInfo]:
        """List all bricks in the workspace."""
        ...

    def get_brick(self, name: str) -> BrickInfo | None:
        """Get information about a specific brick."""
        ...

    def build_index(self) -> dict[str, Any]:
        """Build the BRICKS_INDEX from all BRICK.yaml files."""
        ...


@runtime_checkable
class BrickScaffolder(Protocol):
    """Port: Brick scaffolding operations."""

    def create_component(self, name: str) -> Path:
        """Create a new component brick.
        
        Args:
            name: Component name.
            
        Returns:
            Path to the created component.
        """
        ...

    def create_base(self, name: str) -> Path:
        """Create a new base brick.
        
        Args:
            name: Base name.
            
        Returns:
            Path to the created base.
        """
        ...

    def scaffold_structure(self, brick_path: Path, brick_type: str) -> None:
        """Scaffold the standard brick structure.
        
        Args:
            brick_path: Path to the brick directory.
            brick_type: Type of brick ("component" or "base").
        """
        ...


@runtime_checkable
class ComplianceChecker(Protocol):
    """Port: Compliance checking operations."""

    def check_all(self, workspace_root: Path | None = None) -> ComplianceReport:
        """Run all compliance checks.
        
        Args:
            workspace_root: Root directory of the workspace.
            
        Returns:
            Compliance report with all violations.
        """
        ...

    def check_import_integrity(
        self,
        workspace_root: Path | None = None,
    ) -> dict[str, Any]:
        """Check that all imports in brick source files can be resolved."""
        ...

    def check_branch_naming(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Check git branch naming convention."""
        ...

    def check_file_sizes(
        self,
        workspace_root: Path | None = None,
        max_lines: int = 200,
    ) -> dict[str, Any]:
        """Check that files stay under line limit."""
        ...

    def check_bricks_index(self, workspace_root: Path | None = None) -> dict[str, Any]:
        """Validate BRICKS_INDEX.yaml exists and is valid."""
        ...
