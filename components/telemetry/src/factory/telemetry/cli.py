"""Telemetry Module CLI.

Commands:
  telemetry-module run --config ./config
"""

from __future__ import annotations

import sys
from pathlib import Path

import click

from factory.telemetry.runtime.runtime import TelemetryRuntime
from factory.telemetry.server import create_mcp_server


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Telemetry Module - portable OTLP telemetry as MCP tools."""


@cli.command()
@click.option("--config", "config_dir", default="./config", help="Path to config directory")
def run(config_dir: str) -> None:
    """Start the MCP server (stdio)."""
    cfg = Path(config_dir)
    runtime = TelemetryRuntime(config_dir=cfg)
    runtime.initialize()

    mcp = create_mcp_server(runtime)

    # stdout is reserved for MCP protocol
    sys.stderr.write(f"Telemetry module initialized with config: {cfg}\n")
    sys.stderr.write("Starting MCP server (stdio)...\n")
    mcp.run()
