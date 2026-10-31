"""Project scaffolding - generates Polylith project from a list of bricks.

Creates projects/<name>/ with pyproject.toml, README.md, Dockerfile,
docker-compose.yml, Makefile, and .env.example — deployment-ready
from creation.
"""

from pathlib import Path
from typing import Any

from .deps import resolve_dependencies
from .scaffold_docker import generate_compose, generate_dockerfile
from .scaffold_make import generate_env_example, generate_makefile


def _brick_type(name: str, workspace_root: Path) -> str:
    """Determine if a brick is a component or base."""
    return "base" if (workspace_root / "bases" / name).exists() else "component"


def _available_bases(workspace_root: Path) -> list[str]:
    """List all base brick names in the workspace."""
    bases_dir = workspace_root / "bases"
    if not bases_dir.exists():
        return []
    return sorted(
        d.name for d in bases_dir.iterdir()
        if d.is_dir() and not d.name.startswith(".")
        and (d / "src" / "factory" / d.name).exists()
    )


def _suggest_bases(components: list[str], workspace_root: Path) -> list[dict[str, Any]]:
    """Rank available bases by overlap with requested components."""
    bases = _available_bases(workspace_root)
    if not bases:
        return []
    requested = set(components)
    suggestions = []
    for base in bases:
        deps = set(resolve_dependencies([base], workspace_root)["resolved"]) - {base}
        overlap = deps & requested
        suggestions.append({"base": base, "connects_to": sorted(overlap), "overlap_count": len(overlap)})
    suggestions.sort(key=lambda s: (-s["overlap_count"], s["base"]))
    return suggestions


def _brick_path(name: str, brick_type: str) -> str:
    """Return the relative polylith brick mapping for pyproject.toml."""
    prefix = "bases" if brick_type == "base" else "components"
    return f"../../{prefix}/{name}/src/factory/{name}"


def _generate_pyproject(
    name: str, description: str, resolved_bricks: list[str],
    packages: list[str], workspace_root: Path,
) -> str:
    """Generate pyproject.toml content for a project."""
    brick_lines = []
    for brick in sorted(resolved_bricks):
        bt = _brick_type(brick, workspace_root)
        path = _brick_path(brick, bt)
        brick_lines.append(f'"{path}" = "factory/{brick}"')
    bricks_section = "\n".join(f"    {line}" for line in brick_lines)

    core_deps = ['"mcp[cli]==2.1.1"', '"pydantic>=2.0.0"', '"pyyaml>=6.0.0"']
    core_names = {c.strip('"').split(">=")[0].split("[")[0] for c in core_deps}
    extra = [f'"{p}"' for p in packages if p.split(">=")[0].split("[")[0] not in core_names]
    all_deps = sorted(set(core_deps + extra))
    deps_section = "\n".join(f"    {d}," for d in all_deps)

    return f"""[build-system]
requires = ["hatchling", "hatch-polylith-bricks"]
build-backend = "hatchling.build"

[project]
name = "{name}"
version = "0.1.0"
description = "{description}"
requires-python = ">=3.11"

dependencies = [
{deps_section}
]

[project.optional-dependencies]
test = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
]

[tool.hatch.build.targets.wheel]
packages = ["factory"]

[tool.hatch.build.hooks.polylith-bricks]

[tool.polylith.bricks]
{bricks_section}
"""


def _generate_readme(name: str, description: str, resolved_bricks: list[str]) -> str:
    """Generate README.md content for a project."""
    brick_list = "\n".join(f"- `{b}`" for b in sorted(resolved_bricks))
    return f"""# Project: {name}

{description}

## Bricks

{brick_list}

## Run

```bash
uv run --project projects/{name} python -m factory.<entry_module>
```

## Config

See `pyproject.toml` for the full brick map and dependencies.
"""


def create_project(
    name: str, bricks: list[str], description: str = "",
    workspace_root: Path | None = None,
    include_adapters: list[str] | None = None,
) -> dict[str, Any]:
    """Scaffold a Polylith project with pyproject.toml and README."""
    if workspace_root is None:
        workspace_root = Path.cwd()

    project_dir = workspace_root / "projects" / name
    if project_dir.exists():
        return {"status": "error", "error": f"Project '{name}' already exists at {project_dir}"}

    dep_result = resolve_dependencies(bricks, workspace_root, include_adapters)
    if dep_result["not_found"]:
        return {"status": "error", "error": f"Bricks not found: {dep_result['not_found']}"}

    resolved = dep_result["resolved"]
    packages = dep_result["python_packages"]

    # Enforce: every project must include at least one base brick
    has_base = any(_brick_type(b, workspace_root) == "base" for b in resolved)
    if not has_base:
        comps = [b for b in resolved if _brick_type(b, workspace_root) == "component"]
        return {
            "status": "error",
            "error": (
                "No base brick in project. Every project needs a base "
                "as its entry point (e.g. mcp_server, api, dashboard)."
            ),
            "available_bases": _available_bases(workspace_root),
            "suggested_bases": _suggest_bases(comps, workspace_root),
            "resolved_components": comps,
        }

    if not description:
        description = f"Polylith project packaging: {', '.join(sorted(bricks))}"

    # Classify bricks into bases and components
    bases = [b for b in resolved if _brick_type(b, workspace_root) == "base"]
    components = [b for b in resolved if _brick_type(b, workspace_root) == "component"]

    project_dir.mkdir(parents=True)
    (project_dir / "pyproject.toml").write_text(
        _generate_pyproject(name, description, resolved, packages, workspace_root)
    )
    (project_dir / "README.md").write_text(
        _generate_readme(name, description, resolved)
    )
    (project_dir / "Dockerfile").write_text(
        generate_dockerfile(name, bases)
    )
    (project_dir / "docker-compose.yml").write_text(
        generate_compose(name, bases, components)
    )
    (project_dir / "Makefile").write_text(
        generate_makefile(name, bases)
    )
    (project_dir / ".env.example").write_text(
        generate_env_example(name, bases, components)
    )

    files_created = [
        "pyproject.toml", "README.md", "Dockerfile",
        "docker-compose.yml", "Makefile", ".env.example",
    ]
    return {
        "status": "success",
        "path": str(project_dir),
        "bricks": dep_result,
        "files_created": files_created,
    }
