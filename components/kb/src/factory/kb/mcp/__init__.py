"""MCP primitives for KB brick.

This package contains:
- tools/: Tool registration (deterministic, operational, authoring)
- resources.py: Static/queryable data (schemas, docs, collections)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from .tools import register_tools
from . import docs, templates, resources, prompts

__all__ = ["register_tools", "docs", "templates", "resources", "prompts"]
