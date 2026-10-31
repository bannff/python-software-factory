"""Prompt templates for Foreman MCP prompts."""

MIGRATE_REPO_TEMPLATE = """# Repository Migration Analysis

You are analyzing a repository for recreation in Python Factory.

## Source Repository
URL: {source_repo_url}
Description: {source_description}

## Factory Context
Use `foreman_build_bricks_index` to get the current brick inventory.
Factory tenets: MCP-first, <200 LOC, adapter pattern via runtime/ports.py, no cross-imports.

## Analysis Workflow

### Step 1: Deep Source Analysis
Use the **context-gatherer sub-agent** to analyze the source repository:
- Identify all entry points (CLI, API, MCP tools)
- Catalog capabilities and use cases (what does it DO, not how)
- Map dependencies and external integrations
- Note any domain-specific logic worth preserving

### Step 2: Capability Mapping
For each capability identified, determine:
- **EXISTS**: Factory brick already covers this
- **EXTEND**: Factory brick needs minor extension
- **GAP**: New brick required

Output as structured table:
| Capability | Description | Factory Brick | Status | Notes |
|------------|-------------|---------------|--------|-------|

### Step 3: Gap Analysis
For each GAP, define the new brick:
- Proposed name (lowercase, underscore-separated)
- Type: component or base
- Why existing bricks don't cover it
- Proposed features list
- Adapter pattern needs (what backends should be pluggable?)

### Step 4: Project Assembly Plan
- Project location: `projects/{project_name}/`
- Required bricks (existing + new)
- Dependency order for new brick creation
- Integration test scenarios

### Step 5: GitHub Issues
Generate issue content for:
1. **Parent issue**: "Recreate {repo_name} in Factory"
   - Summary of migration
   - Links to sub-issues
   - Acceptance criteria
2. **Sub-issues**: One per GAP brick
   - Use `type:scaffold` label
   - Include BRICK.yaml draft
   - List features and adapters

## Tools to Use
- `foreman_build_bricks_index` - Get current brick inventory
- `foreman_guardian_check` - Validate compliance after changes
- `foreman_create_component` / `foreman_create_base` - Scaffold new bricks
- GitHub tools to create issues

## Output Format
Produce a complete migration plan document that can be:
1. Reviewed by a human
2. Used as input for subsequent brick creation
3. Logged to GitHub as the parent issue body

Remember: We are RECREATING, not migrating. The source repo is a requirements doc.
The factory stays pristine - if something doesn't fit, the factory grows to accommodate it properly.
"""

CREATE_COMPONENT_TEMPLATE = """Create a new component brick named "{name}" with the following details:

Description: {description}
Features: {features}

## Steps

1. Run: `uvx --from polylith-cli poly create component name:{name}`

2. Create BRICK.yaml at `components/{name}/BRICK.yaml`:
```yaml
name: {name}
type: component
namespace: factory.{name}
description: {description}
mcp_enabled: true
features:
{features_yaml}
```

3. Create the standard structure:
- `components/{name}/src/factory/{name}/__init__.py`
- `components/{name}/src/factory/{name}/interface.py` (public API)
- `components/{name}/src/factory/{name}/server.py` (MCP tools)
- `components/{name}/src/factory/{name}/core.py` (business logic)

4. Implement the MCP contract (get_capabilities, health_check, describe_config_schema)

5. Verify: `foreman_guardian_check`
"""

FIX_COMPLIANCE_TEMPLATE = """Fix compliance violations in the workspace.

## Current Issues

{violations}

## Resolution Steps

### For file size violations (>200 LOC):
1. Identify the large file
2. Split into logical modules:
   - `mcp/` subpackage for MCP tools (deterministic.py, operational.py, authoring.py)
   - `runtime/` subpackage for business logic
3. Keep each file under 200 lines
4. Re-run `foreman_guardian_check`

### For branch naming violations:
1. Rename branch to follow pattern: `feat/<issue>-*`, `fix/<issue>-*`, or `chore/<issue>-*`
2. Example: `git branch -m feat/46-unified-mcp-server`

### For BRICKS_INDEX issues:
1. Run `foreman_write_bricks_index` to regenerate
2. Commit the updated BRICKS_INDEX.yaml

### For import integrity failures:
1. Review the unresolved imports
2. Add missing dependencies to pyproject.toml
3. Or fix the import statement if it's a typo
4. Re-run `foreman_guardian_check`
"""

ONBOARD_AGENT_TEMPLATE = """# Python Factory Onboarding

Welcome to the Python Factory workspace. Here's how to work effectively:

## Architecture

This is a Polylith monorepo where every brick exposes an MCP interface.

- **components/**: Reusable logic bricks (auth, kb, workflow, etc.)
- **bases/**: Entry points (dashboard, mcp_server, blueprint)
- **projects/**: Deployable artifacts

## Key Tools

Use these foreman tools for workspace operations:
- `foreman_info` - Workspace overview
- `foreman_check` - Polylith integrity
- `foreman_guardian_check` - Full compliance gate
- `foreman_get_repo_guardrails` - Operating model
- `foreman_build_bricks_index` - Regenerate brick index

## Workflow

1. Create/confirm a GitHub Issue with acceptance criteria
2. Create branch: `feat/<issue>-*`, `fix/<issue>-*`, or `chore/<issue>-*`
3. Implement changes (keep files <200 LOC)
4. Verify: `foreman_guardian_check`
5. Open PR with `Fixes #<issue>`

## Resources

- `foreman://docs/overview` - Polylith architecture
- `foreman://docs/brick_contract` - MCP contract requirements
- `foreman://docs/workflow` - Development workflow
- `foreman://bricks` - Current brick inventory
"""
