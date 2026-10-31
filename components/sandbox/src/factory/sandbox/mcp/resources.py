"""MCP Resource registration for sandbox brick.

Resources expose static/queryable data:
- Schemas for sandbox configuration and environments
- Documentation on adapters and usage
- Live environment data
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from typing import Any

if TYPE_CHECKING:
    from ..runtime.runtime import SandboxRuntime

DOCS = {
    "overview": """# Sandbox Component

Remote execution environment provisioning with pluggable infrastructure adapters.

## Adapters

- **aws_ec2**: EC2 instances with SSM for command execution
- **aws_ssm**: SSM-managed instances (existing fleet)
- **mock**: Mock adapter for testing

## Usage

```python
from factory.sandbox.interface import Runtime, create_server
from factory.sandbox.runtime.adapters.mock import MockAdapter

adapter = MockAdapter()
runtime = Runtime(adapter)

env = await runtime.provision()
result = await runtime.execute(env.env_id, "echo hello")
await runtime.terminate(env.env_id)
```
""",
    "adapters": """# Sandbox Adapters

## AWS EC2 Adapter
Provisions EC2 instances on-demand with SSM agent for command execution.

## AWS SSM Adapter
Uses existing SSM-managed instances from your fleet.

## Mock Adapter
For testing without real infrastructure.
""",
}


def register(mcp: Any, runtime: "SandboxRuntime") -> None:
    """Register all sandbox resources with the MCP server."""
    from ..runtime.models import SandboxConfig, EnvironmentInfo

    @mcp.resource("sandbox://schemas/config")
    def resource_config_schema() -> str:
        """Get the JSON schema for sandbox configuration."""
        return json.dumps(SandboxConfig.model_json_schema(), indent=2)

    @mcp.resource("sandbox://schemas/environment")
    def resource_environment_schema() -> str:
        """Get the JSON schema for sandbox environments."""
        return json.dumps(EnvironmentInfo.model_json_schema(), indent=2)

    @mcp.resource("sandbox://docs")
    def resource_docs_list() -> str:
        """List available sandbox documentation."""
        docs = [{"name": k, "title": k.replace("_", " ").title()} for k in DOCS.keys()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("sandbox://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get sandbox documentation by name."""
        if doc_name in DOCS:
            return DOCS[doc_name]
        available = list(DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("sandbox://environments")
    def resource_environments() -> str:
        """List sandbox environments."""
        envs = runtime.list_environments()
        return json.dumps(
            {"environments": [e.model_dump() for e in envs], "count": len(envs)},
            indent=2,
        )

    @mcp.resource("sandbox://backends")
    def resource_backends() -> str:
        """List available sandbox backends."""
        return json.dumps({
            "backends": [
                {"name": "aws_ec2", "description": "EC2 instances with SSM"},
                {"name": "aws_ssm", "description": "SSM-managed instances"},
                {"name": "mock", "description": "Mock adapter for testing"},
            ],
        }, indent=2)

    @mcp.resource("sandbox://health")
    def resource_health() -> str:
        """Get sandbox health status."""
        envs = runtime.list_environments()
        running_count = len([e for e in envs if e.status == "running"])
        return json.dumps({
            "healthy": True,
            "adapter": runtime.adapter.__class__.__name__,
            "environments": {
                "total": len(envs),
                "running": running_count,
            },
            "message": "Sandbox runtime operational",
        }, indent=2)

    @mcp.resource("sandbox://factory")
    def resource_factory_ref() -> str:
        """Reference to factory-level resources."""
        return json.dumps({
            "message": "For workspace-level operations, use foreman tools",
            "foreman_tools": [
                "foreman_info", "foreman_check",
                "foreman_guardian_check", "foreman_get_repo_guardrails",
            ],
            "foreman_resources": [
                "foreman://docs", "foreman://bricks", "foreman://schema/brick-yaml",
            ],
        }, indent=2)
