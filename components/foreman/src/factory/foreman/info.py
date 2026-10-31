"""Compact workspace introspection for agent consumption."""

from pathlib import Path
from typing import Any
import tomllib


def workspace_info(workspace_root: Path | None = None) -> dict[str, Any]:
    """Return a compact, structured workspace summary for agent consumption.

    Unlike ``poly info`` (Rich table), this returns a small JSON-friendly dict
    that won't bloat an LLM's context window.
    """
    if workspace_root is None:
        workspace_root = Path.cwd()
    else:
        workspace_root = Path(workspace_root)

    components: list[str] = []
    bases: list[str] = []

    comp_dir = workspace_root / "components"
    if comp_dir.exists():
        components = sorted(
            d.name for d in comp_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    bases_dir = workspace_root / "bases"
    if bases_dir.exists():
        bases = sorted(
            d.name for d in bases_dir.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        )

    # Discover projects and their brick wiring
    projects: dict[str, list[str]] = {}
    proj_dir = workspace_root / "projects"
    if proj_dir.exists():
        for p in sorted(proj_dir.iterdir()):
            pyproject = p / "pyproject.toml"
            if p.is_dir() and pyproject.exists():
                try:
                    with open(pyproject, "rb") as f:
                        data = tomllib.load(f)
                    # [tool.polylith.bricks] is a flat dict:
                    #   "../../components/agent/src/factory/agent" = "factory/agent"
                    # Extract brick names from the target values (last path segment).
                    bricks_map = (
                        data.get("tool", {}).get("polylith", {}).get("bricks", {})
                    )
                    wired = sorted(
                        v.split("/")[-1] for v in bricks_map.values() if isinstance(v, str)
                    )
                    projects[p.name] = wired
                except Exception:
                    projects[p.name] = []

    return {
        "success": True,
        "workspace": workspace_root.name,
        "components_count": len(components),
        "bases_count": len(bases),
        "projects_count": len(projects),
        "components": components,
        "bases": bases,
        "projects": projects,
    }
