from __future__ import annotations

from pathlib import Path

import typer

from factory.auth.runtime.runtime import AuthRuntime
from factory.auth.server import create_mcp_server

cli = typer.Typer(add_completion=False)


@cli.command()
def run(
    config_dir: Path = typer.Option(..., "--config-dir", exists=True, file_okay=False, dir_okay=True),
) -> None:
    """Run the auth-module MCP server over stdio."""
    runtime = AuthRuntime(config_dir=config_dir)
    mcp = create_mcp_server(runtime)
    # FastMCP.run() manages its own event loop
    mcp.run()
