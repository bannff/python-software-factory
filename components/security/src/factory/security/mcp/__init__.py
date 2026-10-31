"""MCP primitives for security brick.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful security operations
- authoring.py: Security-gated configuration changes
- resources.py: Static/queryable data (schemas, docs, findings)
- prompts.py: Guided workflows for common tasks
"""

from . import deterministic, operational, authoring
from .resources import register as register_resources
from .prompts import register as register_prompts

__all__ = [
    "deterministic",
    "operational",
    "authoring",
    "register_resources",
    "register_prompts",
]
