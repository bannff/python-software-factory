"""UIView definitions for the production LangChain/LangGraph Agent surfaces."""
from __future__ import annotations

from typing import Any

from factory.mcp_utils.interface import ToolResult, deterministic, ok

from .contracts.discovery import EmptyInput, ViewsOutput
from .views_tabs import registry_read_tabs


def register(mcp: Any) -> None:
    @mcp.tool()
    @deterministic(input_model=EmptyInput, output_model=ViewsOutput)
    def agent_get_views() -> ToolResult[ViewsOutput]:
        return ok(ViewsOutput(views=[_chat_panel(), _registry_panel()]))


def _chat_panel() -> dict[str, Any]:
    return {
        "id": "agent-chat", "name": "Agent Chat", "brick": "agent", "icon": "💬",
        "layout": {"type": "flex", "direction": "column"},
        "components": [{
            "id": "agent-chat-page", "type": "page",
            "props": {
                "title": "Agent Chat", "subtitle": "Chat with registered AI agents",
                "icon": "💬", "gradient": "from-blue-500 to-indigo-600",
                "tooltip": "Powered by the LangChain/LangGraph runtime",
            },
            "children": [
                {"id": "ac-agents", "type": "metric", "props": {
                    "zone": "info", "label": "Agents", "value": "0", "icon": "users",
                    "data_tool": "agent_get_agent_registry",
                }},
                {"id": "ac-chat", "type": "chat", "props": {
                    "agent_name": "Agent", "agent_initials": "AI", "tool": "agent_reason",
                    "welcome_message": "Hello! Ask me anything.",
                }},
            ],
        }],
        "metadata": {"nav_label": "Agent Chat", "nav_order": 5},
    }


def _registry_panel() -> dict[str, Any]:
    return {
        "id": "agent-registry", "name": "Agent Registry", "brick": "agent", "icon": "📋",
        "layout": {"type": "flex", "direction": "column"},
        "components": [{
            "id": "agent-reg-page", "type": "page",
            "props": {
                "title": "Agent Registry", "subtitle": "Browse agents, swarms, and graphs",
                "icon": "📋", "gradient": "from-slate-500 to-gray-600",
            },
            "children": [
                {"id": "ar-agents", "type": "metric", "props": {
                    "zone": "info", "label": "Agents", "value": "0", "icon": "users",
                    "data_tool": "agent_get_agent_registry",
                }},
                {"id": "ar-graphs", "type": "metric", "props": {
                    "zone": "info", "label": "Graphs", "value": "0", "icon": "chart",
                    "data_tool": "agent_get_graph_registry",
                }},
                {"id": "ar-form", "type": "form", "props": {
                    "zone": "controls", "tool": "agent_reason", "submit_label": "Quick Reason ▶",
                    "fields": [{"name": "task", "label": "Task", "type": "textarea",
                                "placeholder": "Ask the orchestrator..."}],
                }},
                registry_read_tabs(),
            ],
        }],
        "metadata": {"nav_label": "Agent Registry", "nav_order": 7},
    }
