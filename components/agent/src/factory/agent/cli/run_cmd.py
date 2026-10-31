"""Run command - start the Super Agent MCP server."""

import asyncio
import sys
from typing import Any, TYPE_CHECKING

import click

if TYPE_CHECKING:
    from factory.agent import SuperAgent


@click.command()
@click.option("--config", "-c", default="./config", help="Path to config directory")
@click.option(
    "--transport",
    "-t",
    default="stdio",
    type=click.Choice(["stdio", "http"]),
    help="Transport mode",
)
@click.option("--port", "-p", default=8000, help="Port for HTTP transport")
@click.option("--host", default="0.0.0.0", help="Host for HTTP transport")
def run(config: str, transport: str, port: int, host: str) -> None:
    """Start the Super Agent MCP server."""
    from factory.agent import SuperAgent

    agent = asyncio.run(_initialize_agent(config))
    _log_status(agent, config)

    if transport == "stdio":
        _run_stdio(agent)
    else:
        _run_http(agent, host, port)


async def _initialize_agent(config: str) -> "SuperAgent":
    """Initialize the agent asynchronously."""
    from factory.agent import SuperAgent
    agent = SuperAgent(config_dir=config)
    await agent.initialize()
    return agent


def _log_status(agent: "SuperAgent", config: str) -> None:
    """Log agent status to stderr."""
    sys.stderr.write(f"Super Agent initialized with config from: {config}\n")
    sys.stderr.write(
        f"Loaded {len(agent.agent_registry.agents if agent.agent_registry else [])} agents\n"
    )
    sys.stderr.write(
        f"Loaded {len(agent.swarm_registry.swarms if agent.swarm_registry else [])} swarms\n"
    )
    sys.stderr.write(
        f"Loaded {len(agent.graph_registry.graphs if agent.graph_registry else [])} graphs\n"
    )


def _run_stdio(agent: "SuperAgent") -> None:
    """Run in stdio mode."""
    sys.stderr.write("Starting MCP server (stdio)...\n")
    agent.mcp.run()


def _run_http(agent: "SuperAgent", host: str, port: int) -> None:
    """Run in HTTP mode."""
    sys.stderr.write(f"Starting MCP server (HTTP) on {host}:{port}...\n")
    try:
        import uvicorn
        from fastapi import FastAPI

        app = FastAPI(title="Super Agent")
        app.mount("/mcp", agent.mcp.streamable_http_app())

        @app.get("/health")
        def health() -> dict[str, Any]:
            return agent.health_check()

        uvicorn.run(app, host=host, port=port)
    except ImportError:
        sys.stderr.write("Error: HTTP mode requires 'fastapi' and 'uvicorn'\n")
        sys.stderr.write("Install with: pip install super-agent[http]\n")
        raise SystemExit(1)
