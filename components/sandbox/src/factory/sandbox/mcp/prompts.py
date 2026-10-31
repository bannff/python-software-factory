"""MCP Prompt registration for sandbox brick.

Prompts provide guided workflows for common tasks:
- Provisioning environments
- Executing commands
- Debugging environment issues
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register all sandbox prompts with the MCP server."""

    @mcp.prompt()
    def provision_environment(instance_type: str = "t3.micro", purpose: str = "") -> str:
        """Generate guidance for provisioning a sandbox environment."""
        return f"""Provision a sandbox environment for: {purpose or "general use"}

Steps:
1. Provision: sandbox.provision(instance_type="{instance_type}")
2. Wait for running status: sandbox.get_status(env_id)
3. Execute setup commands as needed: sandbox.execute(env_id, "command")
4. Remember to terminate when done: sandbox.terminate(env_id)

The environment will auto-terminate after the configured timeout (default: 1 hour)."""

    @mcp.prompt()
    def execute_command(env_id: str, command: str) -> str:
        """Generate guidance for executing a command in sandbox."""
        return f"""Execute command in sandbox {env_id}:

Command: {command}

Steps:
1. Check environment status: sandbox.get_status("{env_id}")
2. Execute: sandbox.execute("{env_id}", "{command}")
3. Check exit_code in result for success/failure
4. Review stdout/stderr for output

For long-running commands, consider increasing timeout_seconds."""

    @mcp.prompt()
    def debug_environment(env_id: str) -> str:
        """Generate guidance for debugging a sandbox environment."""
        # Try to get current environment info
        envs = runtime.list_environments()
        env = next((e for e in envs if e.env_id == env_id), None)
        if env:
            status_info = f"""- Status: {env.status}
- Instance Type: {env.instance_type}
- Public IP: {env.public_ip or 'N/A'}
- Private IP: {env.private_ip or 'N/A'}"""
        else:
            status_info = "(Environment not found - may have been terminated)"

        return f"""Debug sandbox environment {env_id}:

Current Status:
{status_info}

Debugging Steps:
1. Check status: sandbox.get_status("{env_id}")
2. List all environments: sandbox.list_environments()
3. Try simple command: sandbox.execute("{env_id}", "echo test")
4. Check connectivity: sandbox.execute("{env_id}", "curl -s ifconfig.me")

If environment not found, it may have been terminated or timed out."""
