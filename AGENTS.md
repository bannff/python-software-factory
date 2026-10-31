# Python Factory agent handbook bootstrap

The durable canonical handbook is the Git Wiki at the exact revision below. This file is a bounded, portable bootstrap: it does not duplicate the handbook’s substantive rules.

## Pinned revision

```text
WIKI_REMOTE=https://github.com/bannff/python-factory.wiki.git
PINNED_WIKI_SHA=71fca6bb58b2e02c50292b8b1274a948eb8e3c83
```

Tracking issue: [#773 — establish pinned GitHub Wiki agent handbook](https://github.com/bannff/python-factory/issues/773). Review PR: [#774](https://github.com/bannff/python-factory/pull/774).

The GitHub Wiki page/branch tip is browseable navigation only. It is **not** authoritative unless it resolves to `PINNED_WIKI_SHA` for this source checkout.

## Retrieve and verify

Run this from the source checkout containing this file. Use an explicitly empty or nonexistent destination outside the source worktree; the commands fail rather than replacing any existing path.

```bash
set -euo pipefail

WIKI_REMOTE="https://github.com/bannff/python-factory.wiki.git"
PINNED_WIKI_SHA="71fca6bb58b2e02c50292b8b1274a948eb8e3c83"
DESTINATION="${HANDBOOK_WIKI_DIR:-${TMPDIR:-/tmp}/python-factory.wiki.${PINNED_WIKI_SHA}}"

case "$PINNED_WIKI_SHA" in
  [0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f][0-9a-f]) ;;
  *) echo "Invalid pinned Wiki SHA" >&2; exit 1 ;;
esac

test ! -e "$DESTINATION"
git clone "$WIKI_REMOTE" "$DESTINATION"
cd -- "$DESTINATION"
test "$(git remote get-url origin)" = "$WIKI_REMOTE"
git fetch --prune origin
git cat-file -e "${PINNED_WIKI_SHA}^{commit}"
git checkout --detach "$PINNED_WIKI_SHA"
test "$(git rev-parse HEAD)" = "$PINNED_WIKI_SHA"
test -z "$(git status --porcelain)"
```

The handbook is verified only if all commands succeed. The final checks prove the resolved commit and a clean detached worktree; they do not prove branch protection or every repository policy. The pinned Git object is unsigned: its content identity comes from the SHA, while publisher/reviewer provenance is established through the reviewed source-repository PR that introduces this pin.

## Canonical pages in the checked-out Wiki

- `Home.md`
- `Handbook-Governance.md`
- `Engineering-Principles.md`
- `Delivery-Workflow.md`
- `Multi-Agent-Coordination.md`
- `Architecture.md`
- `Component-Brick-Lifecycle.md`
- `Python-Implementation-Skills.md`
- `Validation-Evidence.md`

Start at `Home.md`, then read `Handbook-Governance.md` before using any other page.

## Precedence and failure behavior

Resolve conflicts in this order:

1. System, platform, and user instructions.
2. Executable repository state and enforcement: code, CI, validators, schemas, locked dependencies, and repository settings that were actually verified.
3. The Git Wiki handbook at exactly `PINNED_WIKI_SHA`.
4. Existing host-specific compatibility guidance.
5. Host defaults, remembered/cached guidance, and floating Wiki content.

If the remote, pin, checkout, SHA comparison, or clean-tree check fails, report that the canonical handbook is unavailable or mismatched. Do **not** substitute a floating Wiki branch/page, another checkout, a cache, a nearby commit, or remembered guidance. Continue only under higher-precedence system/platform/user instructions and executable repository rules, plus the documented compatibility snapshot below.

A handbook revision becomes authoritative only when its Wiki revision is reviewed, a source-repository PR pins that exact full SHA here, and that pinning PR merges. A Wiki push alone does not activate it.

## Existing host-specific guidance compatibility snapshot

This first migration preserves host-specific loader/configuration files unchanged. The compatibility snapshot is source commit `3aaf541d3008670b4b05bc7f39cb822de9467416`, containing 145 tracked entries under `.kiro/`, `.github/copilot-instructions.md`, `.github/agents/`, `.github/hooks/`, `.opencode/`, `.vscode/`, and `opencode.json`; its `git ls-tree` manifest SHA-256 is `7185b6114b051916a9e083f710b3a21fe3c78b1dda618f0c5cc11b0c56265afa`.

This records compatibility material only. It does not establish loader/inclusion/conflict-resolution equivalence for Kiro, Copilot, OpenCode, Cursor, Zed, Claude Code, Codex, or any other host. Replacing or reducing host guidance requires a separate reviewed proof that preserves each host’s loading order, conflict handling, and unavailable-Wiki behavior.
