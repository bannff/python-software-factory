"""Brick discovery from BRICKS_INDEX.yaml or project pyproject.toml.

Discovers available MCP-enabled bricks in the workspace by reading
the BRICKS_INDEX.yaml manifest file, or — when a project pyproject.toml
is present — from [tool.polylith.bricks] so each project is self-defining.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass
class BrickInfo:
    """Metadata about a discovered brick."""

    name: str
    namespace: str
    brick_type: str
    mcp_enabled: bool
    mcp_gateway_host: bool = False
    description: str = ""
    features: list[str] | None = None


def _extract_brick_names_from_pyproject(pyproject_path: Path) -> list[str] | None:
    """Extract brick names from [tool.polylith.bricks] in a pyproject.toml.

    Returns a list of brick names if the section exists, else None.
    Each key in [tool.polylith.bricks] is a source path like
    '../../components/agent/src/factory/agent' — the brick name is the
    last path component.
    """
    try:
        import tomllib  # Python 3.11+
    except ImportError:
        try:
            import tomli as tomllib  # type: ignore[no-reuse-def]
        except ImportError:
            return None

    try:
        with open(pyproject_path, "rb") as f:
            data = tomllib.load(f)
        bricks_section = (
            data.get("tool", {}).get("polylith", {}).get("bricks", {})
        )
        if not bricks_section:
            return None
        names = []
        for src_path in bricks_section:
            # e.g. "../../components/agent/src/factory/agent" → "agent"
            name = Path(src_path).name
            if name:
                names.append(name)
        return names if names else None
    except Exception:
        return None


class BrickDiscovery:
    """Discovers MCP-enabled bricks from project pyproject.toml or BRICKS_INDEX.yaml.

    Priority:
    1. PROJECT_PYPROJECT env var — explicit path to a project pyproject.toml
    2. pyproject.toml in workspace root (if it has [tool.polylith.bricks])
    3. BRICKS_INDEX.yaml — global fallback (all bricks in monorepo)
    """

    DEFAULT_INDEX_NAME = "BRICKS_INDEX.yaml"

    def __init__(self, workspace_root: Path | None = None) -> None:
        if workspace_root is None:
            workspace_root = Path(os.environ.get("WORKSPACE_ROOT", "."))
        self.workspace_root = Path(workspace_root)
        self._index_path = self.workspace_root / self.DEFAULT_INDEX_NAME
        # Optional: explicit project pyproject.toml path
        self._project_pyproject: Path | None = None
        project_pyproject_env = os.environ.get("PROJECT_PYPROJECT", "")
        if project_pyproject_env:
            self._project_pyproject = Path(project_pyproject_env)

    def _get_project_brick_names(self) -> list[str] | None:
        """Try to get brick names from a project pyproject.toml."""
        # 1. Explicit env var
        if self._project_pyproject and self._project_pyproject.exists():
            names = _extract_brick_names_from_pyproject(self._project_pyproject)
            if names:
                return names

        # 2. pyproject.toml in workspace root
        root_pyproject = self.workspace_root / "pyproject.toml"
        if root_pyproject.exists():
            names = _extract_brick_names_from_pyproject(root_pyproject)
            if names:
                return names

        return None

    def _load_index(self) -> dict[str, Any]:
        """Load and parse BRICKS_INDEX.yaml."""
        if not self._index_path.exists():
            return {"bricks": {"components": [], "bases": []}}

        with open(self._index_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {"bricks": {"components": [], "bases": []}}

    def _parse_brick(self, brick_data: dict[str, Any], brick_type: str) -> BrickInfo:
        """Parse a single brick entry into BrickInfo."""
        return BrickInfo(
            name=brick_data.get("name", ""),
            namespace=brick_data.get("namespace", ""),
            brick_type=brick_type,
            mcp_enabled=brick_data.get("mcp_enabled", False),
            mcp_gateway_host=brick_data.get("mcp_gateway_host", False),
            description=brick_data.get("description", ""),
            features=brick_data.get("features"),
        )

    def discover_bricks(
        self, mcp_only: bool = True, aggregation_only: bool = False,
    ) -> list[BrickInfo]:
        """Discover indexed bricks, optionally restricted to loadable MCP children."""
        index = self._load_index()
        bricks_section = index.get("bricks", {})
        discovered: list[BrickInfo] = []
        for brick_type, entries in (
            ("component", bricks_section.get("components", [])),
            ("base", bricks_section.get("bases", [])),
        ):
            for brick_data in entries:
                brick = self._parse_brick(brick_data, brick_type)
                if mcp_only and not brick.mcp_enabled:
                    continue
                if aggregation_only and (
                    not brick.mcp_enabled or brick.mcp_gateway_host
                ):
                    continue
                discovered.append(brick)
        return discovered

    def get_brick_names(
        self, mcp_only: bool = True, aggregation_only: bool = False,
    ) -> list[str]:
        """Get indexed names, optionally restricted to loadable MCP children."""
        project_names = self._get_project_brick_names()
        all_names = [
            brick.name
            for brick in self.discover_bricks(mcp_only, aggregation_only)
        ]
        if project_names:
            project_set = set(project_names)
            filtered = [name for name in all_names if name in project_set]
            import logging
            logging.getLogger(__name__).info(
                "Project pyproject.toml defines %d bricks; %d available after filter",
                len(project_names), len(filtered),
            )
            return filtered
        return all_names
