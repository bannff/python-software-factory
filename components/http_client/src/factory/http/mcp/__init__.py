"""MCP primitives for http module.

This package contains:
- deterministic.py: Read-only query tools (capabilities, health, schemas)
- operational.py: Stateful HTTP operations (GET, POST, etc.)
- resources.py: Static/queryable data (schemas, docs, backends)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, resources, prompts

__all__ = ["deterministic", "operational", "resources", "prompts"]
