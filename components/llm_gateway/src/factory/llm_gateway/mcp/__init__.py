"""MCP primitives for llm_gateway module.

This package contains:
- deterministic.py: Read-only query tools (contract tools)
- operational.py: Stateful LLM operations (complete, chat, embed)
- resources.py: Static/queryable data (schemas, docs, backends)
- prompts.py: Guided workflows for common tasks
- docs.py: Documentation content
- templates.py: Prompt templates
"""

from . import deterministic, operational, resources, prompts

__all__ = ["deterministic", "operational", "resources", "prompts"]
