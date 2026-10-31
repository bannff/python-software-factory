"""MCP primitives for notification module.

This package contains:
- deterministic.py: Read-only queries (capabilities, channels, templates)
- operational.py: Notification operations (send, status, list)
- inbox_deterministic.py: Owner-scoped durable inbox reads (list, get)
- inbox_resolve.py: Owner-scoped deep-link target reauthorization (resolve)
- inbox_operational.py: Owner-scoped inbox mark writes (mark-read, mark-all-read)
- authoring.py: Security-gated channel/template configuration
- resources.py: Static/queryable data (schemas, docs, channels)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import (
    deterministic, operational, authoring, resources, prompts,
    inbox_deterministic, inbox_operational, inbox_resolve,
    prefs_deterministic, prefs_operational,
)

__all__ = [
    "deterministic", "operational", "authoring", "resources", "prompts",
    "inbox_deterministic", "inbox_operational", "inbox_resolve",
    "prefs_deterministic", "prefs_operational",
]
