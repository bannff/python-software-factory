"""MCP primitives for sandbox brick.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful sandbox operations
- authoring.py: Security-gated configuration changes
- resources.py: Static/queryable data (schemas, docs, environments)
- prompts.py: Guided workflows for common tasks
"""

from . import authoring, deterministic, deterministic_extended, operational, operational_extended
from .resources import register as register_resources
from .prompts import register as register_prompts

__all__ = [
    "deterministic",
    "deterministic_extended",
    "operational",
    "operational_extended",
    "authoring",
    "register_resources",
    "register_prompts",
]
