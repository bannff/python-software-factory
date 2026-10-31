"""Polylith Interface for ui module."""

from .server import create_mcp_server as create_server
from .runtime.runtime import UIRuntime as Runtime
from .runtime.adapters.htmx_nav import (
    group_by_domain, brick_domain, DOMAIN_ORDER,
)
from .runtime.adapters.htmx_renderers_chat import render_chat_message
from .runtime.ag_ui_mapper_chat import map_chat_stream_event, AGUIStreamState
from .runtime.ag_ui_mapper_activity import (
    ACTIVITY_TOOL_NAMES, AGUIActivityState, map_activity_event,
)
from .runtime.ag_ui_activity_models import (
    NodeActivity, SubagentActivity,
    SubagentGraphActivity, SubagentSwarmActivity,
)
from .runtime.a2ui import (
    ActionRef, ActionRefError, brick_of_view_tool, normalize_view_actions,
    parse_action_ref,
)
from .runtime.a2ui.action_resolve import build_tool_resolver

__all__ = [
    "ACTIVITY_TOOL_NAMES", "AGUIActivityState",
    "AGUIStreamState", "ActionRef", "ActionRefError",
    "DOMAIN_ORDER", "NodeActivity", "Runtime",
    "SubagentActivity", "SubagentGraphActivity", "SubagentSwarmActivity",
    "brick_domain", "brick_of_view_tool", "build_tool_resolver",
    "create_server", "group_by_domain",
    "map_activity_event", "map_chat_stream_event", "normalize_view_actions",
    "parse_action_ref", "render_chat_message",
]
