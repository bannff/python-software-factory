# Agent Hub

Welcome, agent. This folder contains everything you need to work effectively in the Python Software Factory.

## Quick Start

1. Read [`.agents/steering/factory-protocol.md`](../.agents/steering/factory-protocol.md), the single normative operating and architecture authority. Steering files in this folder provide secondary implementation detail and must link back rather than redefine doctrine.
2. **Ensure the local MCP server is running.** All `foreman_*` tools and brick-level tools come from this server — it's your primary interface to the repo.
   - Config: `.kiro/settings/mcp.json` (Kiro IDE loads this automatically)
   - Entry point: `uv run python -m factory.mcp_server.core`
   - The server aggregates all brick servers into one endpoint. Use `list_bricks` to see available bricks, `get_brick_tools` to inspect a brick's tools, and `call_brick_tool` to invoke them.
3. Read `steering/project-overview.md` for current architecture detail
4. Read `steering/workflow.md` for how to create/modify bricks
5. Check `recipes/` for integration playbooks to validate brick combinations
6. **Current work**: See [GitHub Issues](https://github.com/bannff/python-factory/issues) and [Project Board](https://github.com/bannff/python-factory/projects) for WIP
7. **Validate setup**: Run `foreman_guardian_check`, then try a recipe from `recipes/`

## Contents

### `steering/`
Context and guidelines for working in this repo:
- `project-overview.md` - Architecture, core principles, brick contract
- `dev-principles.md` - Architectural, code quality, testing, documentation principles
- `workflow.md` - Development workflow, branch naming, PR requirements
- `brick-anatomy.md` - Standard brick structure and patterns
- `brick-inventory.md` - Current brick status (counts derive from `BRICKS_INDEX.yaml`)
- `beads-workflow.md` - Beads issue tracking, shell safety, session completion
- `mcp-tools.md` - MCP tool patterns and categories
- `hypothesis-testing.md` - Property-based testing guide
- `a2ui-protocol.md` - A2UI/AG-UI rendering protocol
- `circuitron.md` - Hardware brick context

The unified index at `.agents/steering/factory-protocol.md` is always injected and references these files.

### `recipes/`
Integration playbooks for validating brick combinations. Each recipe:
- Describes a realistic scenario combining 2-4 bricks
- Lists the MCP tools to call and expected outcomes
- Is executed by an agent (you), not as a script

Run a recipe by reading the playbook and executing the steps via MCP.

## Key Resources

- `.kiro/settings/mcp.json` - MCP server config (entry point for all tools)
- `BRICKS_INDEX.yaml` - Authoritative list of all bricks
- `foreman_guardian_check` - Run compliance checks
- `foreman_info` - Get workspace overview

## Factory Tenets

1. **MCP-First** - Interact through MCP, not direct imports
2. **Polymorphic** - Use `runtime/ports.py` Protocol interfaces
3. **<200 LOC** - Split large files into `mcp/`, `runtime/` subdirs
4. **No Cross-Imports** - Use `factory.<brick>.interface` only
5. **Clean Architecture** - Business logic in `runtime/`, MCP in `mcp/`
