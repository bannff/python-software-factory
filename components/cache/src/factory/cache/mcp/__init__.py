"""MCP primitives for cache module.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful cache operations (get, set, delete, clear)
- resources.py: Static/queryable data (schemas, docs, stats)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, resources, prompts

__all__ = ["deterministic", "operational", "resources", "prompts"]
