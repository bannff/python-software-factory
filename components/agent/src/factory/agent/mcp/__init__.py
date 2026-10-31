"""MCP primitives for agent brick.

This package contains:
- tools.py: Discovery and reasoning tools (deterministic + operational)
- authoring.py: Configuration management tools (per-surface gated)
- agent_template_tools.py: Persona (agent template) authoring tools
- authoring_capabilities.py: Always-registered per-action capability probe
- resources.py: Static/queryable data (docs, templates, registries)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- docs_content.py: Documentation strings
- templates.py: Prompt templates
"""

from .resources import register as register_resources
from .prompts import register as register_prompts
from .tools import register as register_tools
from .authoring import register as register_authoring
from .agent_template_tools import register as register_agent_templates
from .authoring_capabilities import register as register_authoring_capabilities

__all__ = [
    "register_resources",
    "register_prompts",
    "register_tools",
    "register_authoring",
    "register_agent_templates",
    "register_authoring_capabilities",
]
