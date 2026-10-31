"""Registry tab builder for Agent dashboard views."""
from __future__ import annotations

from typing import Any


def registry_read_tabs() -> dict[str, Any]:
    return {
        "id": "reg-tabs", "type": "tabs",
        "props": {
            "active": "agents",
            "tabs": [
                {"id": "agents", "label": "Agents", "lazy_tool": "agent_get_agent_registry"},
                {"id": "swarms", "label": "Swarms", "lazy_tool": "agent_get_swarm_registry"},
                {"id": "graphs", "label": "Graphs", "lazy_tool": "agent_get_graph_registry"},
            ],
        },
    }
