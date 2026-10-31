---
inclusion: manual
---
# Beads Workflow & Shell Safety

Full reference for `bd` (beads) issue tracking and non-interactive shell commands.

## Quick Reference

```bash
bd ready --json           # Find available work
bd show <id>              # View issue details
bd update <id> --claim    # Claim work atomically
bd close <id> --reason "" # Complete work
bd sync                   # Sync with git
```

## Non-Interactive Shell Commands

ALWAYS use non-interactive flags to avoid hanging on confirmation prompts:

```bash
cp -f source dest         # NOT: cp source dest
mv -f source dest         # NOT: mv source dest
rm -f file                # NOT: rm file
rm -rf directory          # NOT: rm -r directory
```

Other: `scp -o BatchMode=yes`, `ssh -o BatchMode=yes`, `apt-get -y`, `HOMEBREW_NO_AUTO_UPDATE=1 brew`.

## Issue Types & Priorities

Types: `bug`, `feature`, `task`, `epic`, `chore`
Priorities: `0` (critical) → `4` (backlog). Default: `2`.

## Creating Issues

```bash
bd create "Title" --description="Details" -t task -p 2 --json
bd create "Found bug" -p 1 --deps discovered-from:<parent-id> --json
```

## Agent Workflow

1. `bd ready` → find unblocked work
2. `bd update <id> --claim` → claim atomically
3. Work on it
4. Discover new work? → `bd create ... --deps discovered-from:<parent-id>`
5. `bd close <id> --reason "Done"`

## Session Completion (Landing the Plane)

Work is NOT complete until `git push` succeeds.

1. File issues for remaining work
2. Run quality gates if code changed
3. Update issue status (close finished, update in-progress)
4. Push: `git pull --rebase && bd sync && git push`
5. Verify: `git status` must show "up to date with origin"

Rules:
- NEVER stop before pushing
- NEVER say "ready to push when you are" — YOU must push
- If push fails, resolve and retry
