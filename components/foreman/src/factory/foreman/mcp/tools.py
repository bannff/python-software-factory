"""Strict typed MCP tool registration for Foreman."""
from pathlib import Path
from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, operational

from ..core import build_bricks_index, write_bricks_index
from ..deps import resolve_dependencies
from ..deps_sync import sync_brick_deps
from ..guardian import run_all_checks
from ..info import workspace_info
from ..poly import run_poly_command
from ..scaffold import create_project
from .contracts.guardian import GuardianOutput
from .contracts.index import BricksIndexOutput, WriteBricksIndexOutput
from .contracts.inputs import (
    CreateNamedInput,
    CreateProjectInput,
    EmptyInput,
    GuardianCheckInput,
    ResolveDependenciesInput,
    SyncBrickDepsInput,
    WorkspaceInput,
    WriteIndexInput,
)
from .contracts.operations import CreateProjectOutput, DependencyResolution, PolyCommandOutput, SyncBrickDepsOutput
from .contracts.static import CapabilitiesOutput, ConfigSchemaOutput, GuardrailsOutput, HealthOutput, WorkspaceInfoOutput


_DETERMINISTIC = [
    "get_capabilities", "health_check", "describe_config_schema", "foreman_info",
    "foreman_check", "foreman_guardian_check", "foreman_get_repo_guardrails",
    "foreman_build_bricks_index", "foreman_resolve_dependencies",
]
_OPERATIONAL = [
    "foreman_create_component", "foreman_create_base", "foreman_write_bricks_index",
    "foreman_create_project", "foreman_sync_brick_deps",
]


def register(mcp: Any) -> None:
    """Register Foreman's complete strict typed public tool surface."""

    @mcp.tool(name="get_capabilities")
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def get_capabilities() -> ToolResult[CapabilitiesOutput]:
        """Return Foreman's supported features and MCP primitives."""
        return {"schema_version": 1, "features": ["polylith", "scaffolding", "workspace_introspection", "governance"], "tooling": {"deterministic": _DETERMINISTIC, "operational": _OPERATIONAL, "authoring": []}, "resources": ["foreman://docs", "foreman://docs/{doc_name}", "foreman://schema/brick-yaml", "foreman://bricks", "foreman://bricks/components", "foreman://bricks/bases"], "prompts": ["create_component", "fix_compliance", "onboard_agent"]}

    @mcp.tool(name="health_check")
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def health_check() -> ToolResult[HealthOutput]:
        """Report whether Foreman's MCP service is ready."""
        return {"status": "ok", "details": {"server": "foreman", "poly_check": "available_via_foreman_check"}}

    @mcp.tool(name="describe_config_schema")
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        """Return the schema for Foreman's runtime configuration."""
        return {"schema_version": 1, "config_schema": {"type": "object", "additionalProperties": False, "properties": {}}}

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=WorkspaceInfoOutput)
    def foreman_info() -> ToolResult[WorkspaceInfoOutput]:
        """Summarize the current Polylith workspace."""
        return workspace_info()

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=PolyCommandOutput)
    def foreman_check() -> ToolResult[PolyCommandOutput]:
        """Run Polylith's workspace consistency check."""
        return run_poly_command(["check"])

    @mcp.tool()
    @deterministic(input_model=GuardianCheckInput, output_model=GuardianOutput)
    def foreman_guardian_check(workspace_root: str | None = None, max_lines: int = 200, file_size_mode: str = "strict", base_sha: str | None = None) -> ToolResult[GuardianOutput]:
        """Run Foreman's structural, import, and MCP-contract compliance checks."""
        return run_all_checks(Path(workspace_root) if workspace_root else None, max_lines, file_size_mode, base_sha)

    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=GuardrailsOutput)
    def foreman_get_repo_guardrails() -> ToolResult[GuardrailsOutput]:
        """Return the repository's development control-plane guardrails."""
        return {"schema_version": 1, "control_plane": {"system": "github", "work": "issues", "changes": "pull_requests", "decisions": "discussions", "knowledge": "wiki"}, "execution_plane": {"foreman": "polylith scaffolding + structure + governance"}, "workflow_example": ["Create/confirm an Issue with acceptance criteria", "Create a branch: feat/<issue>-... | fix/<issue>-... | chore/<issue>-...", "Implement changes (no shims/rigs/alias packages; no sys.path hacks)", "Verify: foreman_guardian_check (import integrity, branch, LOC, BRICKS_INDEX)", "Open PR with Fixes #<issue>"], "links": {"issues": "https://github.com/bannff/python-factory/issues", "pulls": "https://github.com/bannff/python-factory/pulls", "discussions": "https://github.com/bannff/python-factory/discussions", "wiki": "https://github.com/bannff/python-factory/wiki", "readme": "README.md", "walkthrough": "walkthrough.md"}}

    @mcp.tool()
    @operational(input_model=CreateNamedInput, output_model=PolyCommandOutput)
    def foreman_create_component(name: str) -> ToolResult[PolyCommandOutput]:
        """Create a Polylith component with the supplied name."""
        return run_poly_command(["create", "component", "--name", name])

    @mcp.tool()
    @operational(input_model=CreateNamedInput, output_model=PolyCommandOutput)
    def foreman_create_base(name: str) -> ToolResult[PolyCommandOutput]:
        """Create a Polylith base with the supplied name."""
        return run_poly_command(["create", "base", "--name", name])

    @mcp.tool()
    @deterministic(input_model=WorkspaceInput, output_model=BricksIndexOutput)
    def foreman_build_bricks_index(workspace_root: str | None = None) -> ToolResult[BricksIndexOutput]:
        """Build the workspace's BRICKS_INDEX metadata without writing it."""
        return build_bricks_index(Path(workspace_root) if workspace_root else None)

    @mcp.tool()
    @operational(input_model=WriteIndexInput, output_model=WriteBricksIndexOutput)
    def foreman_write_bricks_index(workspace_root: str | None = None, output_path: str | None = None) -> ToolResult[WriteBricksIndexOutput]:
        """Build and write BRICKS_INDEX metadata for a workspace."""
        return write_bricks_index(workspace_root=Path(workspace_root) if workspace_root else None, output_path=Path(output_path) if output_path else None)

    @mcp.tool()
    @deterministic(input_model=ResolveDependenciesInput, output_model=DependencyResolution)
    def foreman_resolve_dependencies(bricks: list[str], workspace_root: str | None = None, include_adapters: list[str] | None = None) -> ToolResult[DependencyResolution]:
        """Resolve the brick and Python dependencies required by selected bricks."""
        return resolve_dependencies(bricks, Path(workspace_root) if workspace_root else None, include_adapters)

    @mcp.tool()
    @operational(input_model=CreateProjectInput, output_model=CreateProjectOutput)
    def foreman_create_project(name: str, bricks: list[str], description: str = "", workspace_root: str | None = None, include_adapters: list[str] | None = None) -> ToolResult[CreateProjectOutput]:
        """Create a Polylith project composed from the selected bricks."""
        return create_project(name, bricks, description, Path(workspace_root) if workspace_root else None, include_adapters)

    @mcp.tool()
    @operational(input_model=SyncBrickDepsInput, output_model=SyncBrickDepsOutput)
    def foreman_sync_brick_deps(bricks: list[str] | None = None, workspace_root: str | None = None, dry_run: bool = False) -> ToolResult[SyncBrickDepsOutput]:
        """Synchronize declared package dependencies for selected bricks."""
        return sync_brick_deps(bricks, Path(workspace_root) if workspace_root else None, dry_run)
