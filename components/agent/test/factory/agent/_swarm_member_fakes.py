"""Shared fakes for inline swarm-member execution tests (#442).

Only the model boundary is faked; capability scope, persona resolution and
tool projection run for real. Every model call records the system prompt it
was built with and the tool names it was offered.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from factory.agent.registry.defaults import SWARMS_TYPED
from factory.mcp_utils.interface import (
    CapabilityDescriptor, CapabilityResult, CapabilityScope,
)
from factory.mcp_utils.runtime.scoped_capability_client import (
    InMemoryScopedCapabilityClient,
)

# Canonical-name resolution reads the real permissions policy, as production does.
PERMISSIONS_DIR = str(Path(__file__).parents[5] / "config" / "mcp_permissions")
TOOLS = ("devtools_read_file", "devtools_list_dir", "devtools_write_file")
CODE_REVIEW = next(swarm for swarm in SWARMS_TYPED if swarm.id == "code-review")


async def _noop(_request: Any) -> CapabilityResult:
    return CapabilityResult(())


def capability_client() -> InMemoryScopedCapabilityClient:
    """Base authority holds a tool (write) that no swarm member declares."""
    schema = {"type": "object", "properties": {}}
    return InMemoryScopedCapabilityClient(
        CapabilityScope.create("swarm-test", set(TOOLS)),
        tuple(CapabilityDescriptor(name, name, schema) for name in TOOLS),
        {name: _noop for name in TOOLS},
    )


def swarm_config(prompt: str, tools: list[str], *, swarm_id: str = "custom") -> dict:
    """Swarm whose single member id is NOT a registered persona."""
    return {
        "id": swarm_id, "kind": "swarm", "name": swarm_id,
        "entry_point": "report-writer",
        "agents": [{"id": "report-writer", "model": "", "system_prompt": prompt,
                    "tools": tools}],
    }
