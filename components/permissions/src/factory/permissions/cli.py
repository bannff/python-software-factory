from __future__ import annotations

from pathlib import Path

import typer

from factory.permissions.runtime.runtime import PermissionsRuntime
from factory.permissions.server import create_mcp_server


cli = typer.Typer(add_completion=False)


@cli.command("run")
def run(
    config_dir: Path = typer.Option(..., "--config-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run the permissions-module MCP server over stdio."""
    runtime = PermissionsRuntime.from_config_dir(config_dir)
    mcp = create_mcp_server(runtime)
    mcp.run()
