# Scripts

This directory contains automation scripts for the Python Factory workspace.

## Governance

All governance checks are handled by the Foreman guardian — a single source of truth:

```bash
# Via MCP tool (preferred)
foreman_guardian_check

# Or via Python
uv run python -c "from factory.foreman.guardian import run_all_checks; print(run_all_checks())"
```

**What it checks:**
- ✅ Import integrity (no cross-component imports)
- ✅ Branch naming compliance
- ✅ File size limits (<200 LOC)
- ✅ BRICKS_INDEX consistency (all bricks have BRICK.yaml)
- ✅ Project-base wiring

## BRICKS_INDEX.yaml

The `BRICKS_INDEX.yaml` file at the root of the repository is a deterministic inventory of all Polylith bricks (components, bases) in the workspace. It serves as:

1. **Single source of truth** for brick metadata
2. **Governance gate** checked by Foreman guardian
3. **Discovery mechanism** for tools and agents

**Maintenance:**
- Regenerate with `foreman_build_bricks_index` (MCP) or `foreman_write_bricks_index`
- Validated in CI before merge
- Should remain alphabetically sorted within each section for determinism

## Running Locally

Before committing:

```bash
# 1. Run guardian check (import integrity, branch naming, LOC, BRICKS_INDEX)
foreman_guardian_check

# 2. Run tests
uv run pytest
```

All checks must pass before opening a PR.
