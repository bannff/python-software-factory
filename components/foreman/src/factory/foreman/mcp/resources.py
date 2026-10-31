"""MCP Resource registration for Foreman."""

import json
from typing import Any


# Static content for resources
POLYLITH_DOCS = {
    "overview": {
        "title": "Polylith Architecture Overview",
        "content": """# Polylith Architecture

Polylith is a software architecture that applies functional thinking at the system scale.

## Core Concepts

- **Workspace**: The monorepo root containing all code
- **Components**: Reusable building blocks with well-defined interfaces
- **Bases**: Entry points that compose components into runnable artifacts
- **Projects**: Deployable configurations that select which bricks to include

## Key Principles

1. **One place to code**: All code lives in one repo
2. **One way to test**: Consistent testing across all bricks
3. **One way to build**: Unified build process
4. **Explicit dependencies**: No hidden coupling between bricks

## Python Factory Extensions

This repo extends Polylith with:
- BRICK.yaml metadata per brick
- MCP interfaces for agent interaction
- BRICKS_INDEX.yaml for workspace discovery
""",
    },
    "brick_contract": {
        "title": "Brick MCP Contract",
        "content": """# Brick MCP Contract

Every MCP-enabled brick MUST expose these tools:

## Required Tools

### get_capabilities()
Returns machine-readable feature list:
```json
{
  "schema_version": 1,
  "features": ["feature1", "feature2"],
  "tooling": {
    "deterministic": ["tool1", "tool2"],
    "operational": ["tool3"],
    "authoring": ["tool4"]
  }
}
```

### health_check()
Fast readiness probe:
```json
{"status": "ok", "details": {...}}
```

### describe_config_schema()
JSON schema for configuration:
```json
{
  "schema_version": 1,
  "config_schema": {"type": "object", "properties": {...}}
}
```

## Tool Categories

Use decorators from `factory.mcp_utils.interface`:
- `@deterministic` - Pure, no side effects (queries, schemas)
- `@operational` - Stateful but idempotent (CRUD operations)  
- `@authoring` - Security-gated config changes
""",
    },
    "workflow": {
        "title": "Development Workflow",
        "content": """# Development Workflow

## Creating a New Brick

1. Scaffold: `uvx --from polylith-cli poly create component name:<name>`
2. Add BRICK.yaml with metadata
3. Create structure: `__init__.py`, `interface.py`, `server.py`, `core.py`
4. Verify: `foreman_guardian_check`

## Pre-Commit Checklist

1. `foreman_guardian_check` - All compliance checks pass (import integrity, branch, LOC, BRICKS_INDEX)
2. `uv run pytest components/<name>/test` - Tests pass
3. Files under 200 LOC

## Branch Naming

- `feat/<issue>-<description>` - New features
- `fix/<issue>-<description>` - Bug fixes
- `chore/<issue>-<description>` - Maintenance

## PR Requirements

- Link to issue: `Fixes #<issue>`
- All checks pass
- No `sys.path` hacks or shim packages
""",
    },
}

BRICK_YAML_SCHEMA = {
    "type": "object",
    "required": ["name", "type", "namespace"],
    "properties": {
        "name": {"type": "string", "description": "Brick identifier"},
        "type": {"type": "string", "enum": ["component", "base"]},
        "namespace": {"type": "string", "pattern": "^factory\\..+$"},
        "description": {"type": "string"},
        "mcp_enabled": {"type": "boolean", "default": False},
        "mcp_gateway_host": {"type": "boolean", "default": False},
        "features": {"type": "array", "items": {"type": "string"}},
    },
}


def register(mcp: Any, get_bricks_index: Any) -> None:
    """Register all Foreman resources with the MCP server."""

    @mcp.resource("foreman://docs/{doc_name}")
    def resource_docs(doc_name: str) -> str:
        """Get Polylith/workflow documentation."""
        if doc_name in POLYLITH_DOCS:
            return POLYLITH_DOCS[doc_name]["content"]
        available = list(POLYLITH_DOCS.keys())
        return f"Unknown doc: {doc_name}. Available: {available}"

    @mcp.resource("foreman://docs")
    def resource_docs_list() -> str:
        """List available documentation."""
        docs = [{"name": k, "title": v["title"]} for k, v in POLYLITH_DOCS.items()]
        return json.dumps({"docs": docs}, indent=2)

    @mcp.resource("foreman://schema/brick-yaml")
    def resource_brick_schema() -> str:
        """Get the JSON schema for BRICK.yaml files."""
        return json.dumps(BRICK_YAML_SCHEMA, indent=2)

    @mcp.resource("foreman://bricks")
    def resource_bricks_index() -> str:
        """Get the current BRICKS_INDEX."""
        index = get_bricks_index()
        return json.dumps(index, indent=2)

    @mcp.resource("foreman://bricks/components")
    def resource_components() -> str:
        """List all components in the workspace."""
        index = get_bricks_index()
        components = index.get("bricks", {}).get("components", [])
        return json.dumps({"components": components, "count": len(components)}, indent=2)

    @mcp.resource("foreman://bricks/bases")
    def resource_bases() -> str:
        """List all bases in the workspace."""
        index = get_bricks_index()
        bases = index.get("bricks", {}).get("bases", [])
        return json.dumps({"bases": bases, "count": len(bases)}, indent=2)
