"""MCP primitives for logger brick.

This package contains:
- deterministic.py: Contract tools + read-only log queries
- operational.py: Log write operations (info, error, warning, debug)
- authoring.py: Security-gated admin operations (clear)
- resources.py: Static/queryable data (schemas, docs, log queries)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
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
