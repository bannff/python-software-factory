# Development Workflow

## Creating a New Brick

```bash
# 1. Scaffold with polylith
uvx --from polylith-cli poly create component name:<name>

# 2. Add BRICK.yaml
cat > components/<name>/BRICK.yaml << 'EOF'
name: <name>
type: component
namespace: factory.<name>
description: <description>
mcp_enabled: true
features:
  - <feature_1>
EOF

# 3. Create minimal structure
mkdir -p components/<name>/src/factory/<name>/runtime
touch components/<name>/src/factory/<name>/{__init__,interface,server,core}.py
touch components/<name>/src/factory/<name>/runtime/{__init__,runtime}.py

# 4. (Optional) Add AWS adapter — see brick-anatomy.md "AWS Adapter Pattern"
# Create aws.py with service selector + backends/ subfolder if multiple services
# Must expose infrastructure_spec() returning structured resource requirements

# 5. Verify
foreman_guardian_check
```

## Pre-Commit Checklist

1. `foreman_guardian_check` - Strict whole-tree compliance (import integrity, branch, LOC, BRICKS_INDEX, project bases)
2. `uv run pytest components/<name>/test` - Tests pass
3. Files under 200 LOC

## Guardian Gates

Strict Guardian remains the default: `run_all_checks()` and `foreman_guardian_check` inspect the whole tree, and the manual `workflow_dispatch` gate runs that strict mode. Pull requests use an explicit ratchet instead: the candidate is `github.sha`, and `run_all_checks(file_size_mode="ratchet", base_sha=...)` receives only the trusted `github.event.pull_request.base.sha`. There is no merge-base inference or fallback baseline.

The PR ratchet compares debt by stable identity rather than by aggregate count:

- **LOC** — rename-aware path comparison blocks a new Python file over 200 lines, a file that crosses 200 lines, or an already-oversized file that grows. Unchanged, reduced, deleted, and true-renamed legacy files do not block.
- **Project bases** — the identity is `projects/<project>/pyproject.toml`. Compliance is parsed from `[tool.polylith.bricks]` source keys; prose containing `bases/...` does not count. New noncompliant identities block, while unchanged and resolved identities are reported as `legacy_violations` and `resolved_violations`. Renaming a noncompliant project creates a new identity.

Both ratchets fail closed when the base SHA is missing, malformed, or unresolvable, or when required Git data, files, or TOML cannot be read. Existing strict debt is not hidden: PR checks publish the separate strict LOC report, project-base ratchet output retains legacy debt, and manual dispatch runs the full strict Guardian.

## Branch Discipline

**NEVER create a new feature branch while another is unmerged.** Merge or close the current branch's PR before starting new work. This prevents divergent branches that touch the same files and accumulate merge debt.

## Branch Naming

- `feat/<issue>-<description>` - New features
- `fix/<issue>-<description>` - Bug fixes
- `chore/<issue>-<description>` - Maintenance

## PR Requirements

- Link to issue: `Fixes #<issue>`
- All checks pass
- No `sys.path` hacks or shim packages

## Foreman MCP Tools (python-factory server)

Use foreman for workspace operations:
- `foreman_info` - Workspace overview
- `foreman_check` - Polylith structure info (informational only)
- `foreman_guardian_check` - Full compliance gate (import integrity + branch + LOC + BRICKS_INDEX)
- `foreman_get_repo_guardrails` - Operating model for agents
- `foreman_create_component` - Scaffold new component
- `foreman_create_base` - Scaffold new base
- `foreman_build_bricks_index` - Regenerate BRICKS_INDEX.yaml

## Foreman MCP Resources

- `foreman://docs` - List available documentation
- `foreman://docs/{doc_name}` - Get specific doc (overview, brick_contract, workflow)
- `foreman://schema/brick-yaml` - BRICK.yaml JSON schema
- `foreman://bricks` - Current BRICKS_INDEX
- `foreman://bricks/components` - List components
- `foreman://bricks/bases` - List bases

## Foreman MCP Prompts

- `create_component` - Guide for creating a new component
- `fix_compliance` - Guide for fixing compliance violations
- `onboard_agent` - Onboarding for agents new to this workspace
