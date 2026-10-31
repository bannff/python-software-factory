"""Project introspection — reads pyproject.toml to discover brick graph."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]


# Bases that map to process types / entry points
BASE_PROCESS_MAP: dict[str, dict[str, str]] = {
    "api": {"cmd": "uvicorn", "port": "8000", "description": "FastAPI HTTP server"},
    "mcp_server": {"cmd": "mcp", "port": "", "description": "MCP aggregator"},
    "worker": {"cmd": "worker", "port": "", "description": "Background task worker"},
}

_ADAPTER_RE = re.compile(r"^FACTORY_(\w+)_ADAPTER=(.+)$")


@dataclass
class ProjectInfo:
    """Introspected project metadata."""

    name: str
    description: str
    bases: list[str] = field(default_factory=list)
    components: list[str] = field(default_factory=list)
    scripts: dict[str, str] = field(default_factory=dict)
    infra_services: list[str] = field(default_factory=list)
    adapter_selections: dict[str, str] = field(default_factory=dict)
    python_version: str = "3.13"


def read_adapter_selections(project_dir: Path) -> dict[str, str]:
    """Parse FACTORY_{BRICK}_ADAPTER=value lines from .env or .env.example."""
    env_path = project_dir / ".env"
    if not env_path.exists():
        env_path = project_dir / ".env.example"
    if not env_path.exists():
        return {}

    selections: dict[str, str] = {}
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("#") or not line:
            continue
        m = _ADAPTER_RE.match(line)
        if m:
            brick_name = m.group(1).lower()
            selections[brick_name] = m.group(2).strip()
    return selections


def resolve_infra_from_bricks(
    workspace_root: Path,
    components: list[str],
    selections: dict[str, str],
) -> list[str]:
    """Resolve Docker services needed based on adapter selections and BRICK.yaml."""
    services: set[str] = set()
    for brick in components:
        adapter = selections.get(brick)
        if not adapter:
            continue
        brick_yaml = workspace_root / "components" / brick / "BRICK.yaml"
        if not brick_yaml.exists():
            continue
        data = yaml.safe_load(brick_yaml.read_text()) or {}
        adapter_infra = data.get("adapter_infra", {})
        entry = adapter_infra.get(adapter)
        if entry:
            services.update(entry.get("services", []))
    return sorted(services)


def introspect_project(workspace_root: Path, project_name: str) -> ProjectInfo:
    """Read a project's pyproject.toml and extract brick graph."""
    project_dir = workspace_root / "projects" / project_name
    pyproject_path = project_dir / "pyproject.toml"

    if not pyproject_path.exists():
        raise FileNotFoundError(f"No pyproject.toml at {pyproject_path}")

    with open(pyproject_path, "rb") as f:
        data = tomllib.load(f)

    project_meta = data.get("project", {})
    bricks_map = data.get("tool", {}).get("polylith", {}).get("bricks", {})
    scripts = data.get("project", {}).get("scripts", {})

    bases: list[str] = []
    components: list[str] = []

    for src_path in bricks_map:
        parts = Path(src_path).parts
        if "bases" in parts:
            idx = parts.index("bases")
            if idx + 1 < len(parts):
                bases.append(parts[idx + 1])
        elif "components" in parts:
            idx = parts.index("components")
            if idx + 1 < len(parts):
                components.append(parts[idx + 1])

    selections = read_adapter_selections(project_dir)
    infra_services = resolve_infra_from_bricks(workspace_root, components, selections)

    return ProjectInfo(
        name=project_name,
        description=project_meta.get("description", ""),
        bases=sorted(bases),
        components=sorted(components),
        scripts=dict(scripts),
        infra_services=infra_services,
        adapter_selections=selections,
        python_version="3.13",
    )
