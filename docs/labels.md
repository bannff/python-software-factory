# Label Taxonomy

This document defines the minimal label taxonomy for the python-factory repository. Labels are designed for **agent workflows**: consistent triage, discoverability, deterministic conventions, and minimal cognitive load.

> **Evidence of Usage**: See [label-evidence.md](label-evidence.md) for proof that labels are actively used on 10+ open issues.

## Design Principles

- **Minimal**: Only labels that solve real workflow pain
- **Deterministic**: Clear rules for when to apply each label
- **Agent-friendly**: Consistent naming and categorization
- **Hierarchical**: Category prefixes (status:, type:, brick:, agent:)

## Label Categories

### Status Labels (`status:*`)

Track the lifecycle state of issues and PRs.

| Label | Color | Description | When to Apply |
|-------|-------|-------------|---------------|
| `status:todo` | `fbca04` (yellow) | Not started | Issue created but work hasn't begun |
| `status:in-progress` | `fbca04` (yellow) | Work in progress | Active development underway |
| `status:blocked` | `d73a4a` (red) | Blocked by dependency | Cannot proceed until external condition is met |
| `status:review` | `0e8a16` (green) | Ready for review | Code complete, awaiting human or agent review |
| `status:done` | `0e8a16` (green) | Completed | Work finished, issue can be closed |

**Agent guidance**: 
- Always set exactly one status label per issue/PR
- Update status as work progresses
- Move from `status:todo` → `status:in-progress` → `status:review` → `status:done`

### Type Labels (`type:*`)

Categorize the nature of the work.

| Label | Color | Description | When to Apply |
|-------|-------|-------------|---------------|
| `type:bug` | `d73a4a` (red) | Bug fix | Fixes broken functionality |
| `type:feature` | `0075ca` (blue) | New feature | Adds new capability |
| `type:doc` | `0075ca` (blue) | Documentation | Documentation changes only |
| `type:scaffold` | `0075ca` (blue) | Scaffolding / setup | Infrastructure, tooling, project structure |
| `type:refactor` | `5319e7` (purple) | Refactoring | Code restructuring without behavior change |
| `type:test` | `5319e7` (purple) | Testing | Test additions or improvements |

**Agent guidance**:
- Always set exactly one type label per issue/PR
- Choose the primary intent if multiple types apply
- Use `type:scaffold` for CI, workflows, templates, project setup
- Use `type:doc` only if changes are purely documentation (no code)

### Brick Labels (`brick:*`)

Tag work related to specific Polylith bricks (components/bases).

| Label Pattern | Color | Description | When to Apply |
|---------------|-------|-------------|---------------|
| `brick:<name>` | `e4e669` (light yellow) | Affects specific brick | Work touches a specific component or base |

**Common brick labels**:
- `brick:auth` - Authentication component
- `brick:kb` - Knowledge Base component
- `brick:agent` - Agent orchestration component
- `brick:workflow` - Workflow component
- `brick:foreman` - Foreman (Polylith tooling) component
- `brick:events` - Events component
- *(Add others as needed)*

**Agent guidance**:
- Apply zero or more brick labels (can be multiple if work spans bricks)
- Create new `brick:<name>` labels as bricks are added to the codebase
- Keep brick names lowercase and matching the actual brick directory name

### Agent Labels (`agent:*`)

Identify which agent owns or is assigned to the work.

| Label | Color | Description | When to Apply |
|-------|-------|-------------|---------------|
| `agent:copilot` | `ededed` (gray) | Work owned by Copilot agent | Assigned to GitHub Copilot |
| `agent:foreman` | `ededed` (gray) | Work owned by Foreman agent | Polylith structure/scaffolding tasks |
| `agent:guardian` | `ededed` (gray) | Work owned by Process Guardian | Compliance and governance tasks |

**Agent guidance**:
- Set zero or one agent label per issue
- Use when work is explicitly assigned to an agent
- Omit if work is for human review or unassigned

## Label Application Examples

### Example 1: Documentation Update
```
status:todo
type:doc
```

### Example 2: New Feature in KB Component
```
status:in-progress
type:feature
brick:kb
agent:copilot
```

### Example 3: Bug Fix Across Multiple Bricks
```
status:review
type:bug
brick:auth
brick:kb
```

### Example 4: Scaffolding Work
```
status:todo
type:scaffold
agent:foreman
```

## How to Apply Labels

### Using the Sync Script (Recommended)

The repository includes a script to sync label definitions to GitHub:

```bash
python scripts/sync_labels.py
```

This script:
- Reads label definitions from `labels.yml`
- Creates or updates labels in the GitHub repository
- Is idempotent (safe to run multiple times)

### Manual Application via GitHub UI

1. Navigate to the issue or PR
2. Click "Labels" in the right sidebar
3. Select appropriate labels from each category (status, type, brick, agent)

### Programmatic Application via API

Agents should use the GitHub API or CLI:

```bash
gh issue edit <number> --add-label "status:in-progress,type:feature,brick:kb"
```

Or via GitHub API:
```bash
curl -X POST \
  -H "Authorization: token $GITHUB_TOKEN" \
  https://api.github.com/repos/bannff/python-factory/issues/<number>/labels \
  -d '{"labels":["status:in-progress","type:feature","brick:kb"]}'
```

## Label Management

### Adding New Labels

1. Edit `labels.yml` to add the new label definition
2. Run `python scripts/sync_labels.py` to create it in GitHub
3. Document it in this file if it's a new category or commonly-used label

### Modifying Labels

1. Update the definition in `labels.yml`
2. Run `python scripts/sync_labels.py` to update GitHub
3. Update documentation in this file

### Removing Labels

- **Don't remove labels hastily** - they may be in use on existing issues
- If a label is no longer needed, mark it as deprecated in `labels.yml`
- Remove from the sync file only after confirming no active issues use it

## Automation

Label syncing is automated via GitHub Actions. On push to main, the workflow `.github/workflows/sync-labels.yml` runs to ensure labels are up-to-date.

## FAQ

**Q: Can I have multiple status labels?**  
A: No, use exactly one status label to avoid confusion.

**Q: What if an issue spans multiple types?**  
A: Choose the primary intent. If it's truly mixed, prefer the type that represents the main deliverable.

**Q: When should I create a new brick label?**  
A: When work touches a specific Polylith brick (component or base) and you want to track work for that brick.

**Q: What if labels drift from the definitions?**  
A: Run `python scripts/sync_labels.py` to reset them to the canonical definitions in `labels.yml`.

---

**Last updated**: 2026-01-30  
**See also**: [README.md](../README.md), [Issue #34](https://github.com/bannff/python-factory/issues/34)
