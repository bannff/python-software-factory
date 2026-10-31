"""MCP primitives for UI module.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful view operations (list, get, connect)
- authoring.py: Security-gated view/component creation
- authoring_dashboard.py: Dashboard creation tool
- resources.py: Static/queryable data (schemas, docs)
- prompts.py: Guided workflows for common tasks
- content/: Documentation and template content
"""

from . import deterministic, operational, authoring, authoring_dashboard, resources, prompts

__all__ = [
    "deterministic",
    "operational",
    "authoring",
    "authoring_dashboard",
    "resources",
    "prompts",
]
