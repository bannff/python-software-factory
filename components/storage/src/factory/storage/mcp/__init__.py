"""MCP primitives for storage module.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful storage operations (blob, document CRUD)
- sql_tools.py: SQL storage operations
- graph_tools.py: Graph storage operations
- owner_secrets.py: Public owner-named secret list/set/delete (no read tool)
- resources.py: Static/queryable data (schemas, docs, stats)
- prompts.py: Guided workflows for common tasks
"""

from . import deterministic, operational, sql_tools, graph_tools, owner_secrets, resources, prompts

__all__ = [
    "deterministic",
    "operational",
    "sql_tools",
    "graph_tools",
    "owner_secrets",
    "resources",
    "prompts",
]
