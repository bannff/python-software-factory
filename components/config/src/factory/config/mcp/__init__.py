"""MCP primitives for config module.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful config operations (get, set, delete)
- resources.py: Static/queryable data (schemas, docs, values)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, resources, prompts

__all__ = ["deterministic", "operational", "resources", "prompts"]
