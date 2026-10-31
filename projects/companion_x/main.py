"""Companion-X server entrypoint: unified MCP + REST + SSE + AG-UI on port 8000.

Runs a Streamable HTTP server via the api base's composition root
(``factory.api.main.create_app``), which mounts the MCP aggregator plus the
streaming-aware AG-UI route. Used by both the local Docker Compose stack
(``projects/companion_x/docker-compose.yml``) and the dev shell script
(``scripts/companion-x-ui.sh``).

The MCP server init is deferred (EAGER_LOAD=0) so the process starts fast;
bricks load on first access. State lives in the configured backends
(Neo4j, DynamoDB, etc.), not in process memory.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

# Deferred loading: bricks import on first access, not at startup.
os.environ.setdefault("EAGER_LOAD", "0")
os.environ.setdefault("MCP_DISCOVERY_MODE", "progressive")
os.environ.setdefault("MCP_SERVER_NAME", "companion-x")
os.environ.setdefault(
    "TELEMETRY_CONFIG_DIR", str(Path(__file__).parent / "telemetry"),
)
os.environ.setdefault(
    "WORKFLOW_CONFIG_DIR", str(Path(__file__).parent / "config"),
)
os.environ.setdefault(
    "FACTORY_AGENT_CONFIG_DIR",
    str(Path(__file__).resolve().parents[2] / ".storage" / "agent-config"),
)
os.environ.setdefault("TELEMETRY_REQUIRED", "1")

# bd:python-factory-gtyb7 — promote the namespaced deployment profile to
# AWS_PROFILE before any brick import builds a boto3 default session.
# A dev shell's ambient AWS_PROFILE would otherwise shadow the .env value
# (uv --env-file yields to ambient); COMPANION_X_AWS_PROFILE has no such
# collision. Mirrors bases/api/main.py::_promote_aws_profile.
if (_cx_profile := os.environ.get("COMPANION_X_AWS_PROFILE")):
    os.environ["AWS_PROFILE"] = _cx_profile

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main():
    """Start the unified server: MCP + REST + SSE + AG-UI on port 8000.

    Builds the app through the ``api`` base (``factory.api.main.create_app``)
    rather than ``factory.mcp_server.core.create_app`` directly. The api base
    is the canonical composition root: its REST adapter already mounts the
    unified MCP aggregator (``factory.mcp_server.interface.get_server``) plus
    the streaming-aware AG-UI route (``CHAT_STREAMING``-gated ``stream_chat``
    via ``factory.agent.interface.get_chat_agent_stream``), superseding
    ``mcp_server``'s legacy blocking ``agent_reason`` + ``str(result)``
    fallback route that leaked raw ToolResult envelopes into chat (bd:
    docker-vs-shell chat regression). All env vars set above (discovery mode,
    telemetry, AWS profile) are read the same way through ``get_server()``
    regardless of which composition root calls it, so behavior is unchanged
    except for the AG-UI transport.
    """
    import uvicorn
    from factory.api.main import create_app

    app = create_app()
    if pid_file := os.environ.get("COMPANION_X_API_PID_FILE"):
        Path(pid_file).write_text(str(os.getpid()))
    logger.info(
        "Starting Companion-X unified server via api base "
        "(MCP + REST + SSE + AG-UI streaming, port 8000)",
    )
    host = os.environ.get("FACTORY_API_HOST", "127.0.0.1")
    port = int(os.environ.get("FACTORY_API_PORT", "8000"))
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
