"""Init command - scaffold a new Super Agent project."""

from pathlib import Path
import click


@click.command()
@click.argument("project_name")
@click.option("--config-only", is_flag=True, help="Only create config dir, no pyproject.toml")
def init(project_name: str, config_only: bool) -> None:
    """Scaffold a new Super Agent project."""
    project_path = Path(project_name)
    config_path = project_path / "config"

    # Create directories
    for subdir in ["agents", "swarms", "graphs", "tools"]:
        (config_path / subdir).mkdir(parents=True, exist_ok=True)

    # Create settings.yaml
    _write_settings(config_path)
    
    # Create .gitkeep files
    for subdir in ["agents", "swarms", "graphs"]:
        (config_path / subdir / ".gitkeep").touch()

    # Create tools/__init__.py and example agent
    _write_tools_init(config_path)
    _write_example_agent(config_path)
    _write_main_py(project_path)

    if not config_only:
        _write_pyproject(project_path, project_name)

    click.echo(f"✓ Created {project_name}/ with config structure")
    click.echo("")
    click.echo("Next steps:")
    click.echo(f"  cd {project_name}")
    click.echo("  pip install -e .")
    click.echo("  super-agent run --config ./config")


def _write_settings(config_path: Path) -> None:
    settings_content = """# Super Agent Settings

models:
  orchestrator: us.amazon.nova-pro-v1:0
  agent: us.amazon.nova-lite-v1:0

defaults:
  model: us.amazon.nova-lite-v1:0
  timeout: 300

limits:
  max_handoffs: 20
  max_iterations: 20
  execution_timeout: 900

logging:
  level: INFO
  format: json
"""
    (config_path / "settings.yaml").write_text(settings_content)


def _write_tools_init(config_path: Path) -> None:
    tools_init = '''"""Custom tools for this project.

Use the @tool decorator to register functions as tools:

    from factory.agent import tool

    @tool
    def my_tool(arg1: str) -> dict:
        """Tool description."""
        return {"result": arg1}
"""
'''
    (config_path / "tools" / "__init__.py").write_text(tools_init)


def _write_example_agent(config_path: Path) -> None:
    example_agent = """# Example Agent Configuration
id: example_agent
name: Example Agent
description: A simple example agent
model: us.amazon.nova-lite-v1:0
system_prompt: |
  You are a helpful assistant. Answer questions clearly and concisely.
tools: []
"""
    (config_path / "agents" / "example.yaml").write_text(example_agent)


def _write_main_py(project_path: Path) -> None:
    main_content = '''"""Super Agent entry point."""

import asyncio
import sys
from factory.agent import SuperAgent


async def main() -> None:
    agent = SuperAgent(config_dir="./config")
    await agent.initialize()
    sys.stderr.write("Starting MCP server (stdio)...\\n")
    agent.mcp.run()


if __name__ == "__main__":
    asyncio.run(main())
'''
    (project_path / "main.py").write_text(main_content)


def _write_pyproject(project_path: Path, project_name: str) -> None:
    pyproject = f'''[project]
name = "{project_name}"
version = "0.1.0"
description = "Super Agent project"
requires-python = ">=3.11"

dependencies = [
    "super-agent @ git+https://github.com/<org>/<repo>.git",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-asyncio>=0.21.0",
]
'''
    (project_path / "pyproject.toml").write_text(pyproject)
