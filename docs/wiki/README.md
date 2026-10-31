# GitHub Wiki Handbook

The [GitHub Wiki](https://github.com/bannff/python-factory/wiki) is the canonical handbook only when its checkout is detached at the exact full `PINNED_WIKI_SHA` in root [`AGENTS.md`](../../AGENTS.md). The approved pin is [`71fca6bb58b2e02c50292b8b1274a948eb8e3c83`](https://github.com/bannff/python-factory.wiki/commit/71fca6bb58b2e02c50292b8b1274a948eb8e3c83). Floating Wiki pages, cached copies, branches, and short SHAs are not authoritative.

## Precedence

1. System, platform, and user instructions.
2. Executable repository state and enforcement: code, CI, validators, schemas, locked dependencies, and settings that were actually verified.
3. The GitHub Wiki handbook at the `AGENTS.md`-pinned commit.
4. Existing host-specific compatibility guidance.
5. Host defaults, remembered/cached guidance, and floating Wiki pages.

Repository prose is useful navigation and evidence, but does not outrank the pinned handbook merely by living in this checkout.

## Verify the Handbook

Follow root [`AGENTS.md`](../../AGENTS.md). In summary, clone [`python-factory.wiki`](https://github.com/bannff/python-factory.wiki.git), fetch it, detach at the full pin, and confirm `git rev-parse HEAD` equals that pin with a clean worktree. A missing, malformed, unreachable, or mismatched pin is invalid; do not substitute a branch or nearby commit.

## Change the Handbook

1. Author and review the Wiki revision.
2. Update the root `AGENTS.md` full pin in the associated source PR.
3. Merge the source pin update to activate that handbook revision.

Existing Kiro, Copilot, and OpenCode loaders remain unchanged compatibility snapshots. Their loader/source-resolution semantics require a later equivalence proof; do not imply that this policy has established one.

## Start a Wiki Page

Copy `docs/templates/wiki-page.md`, write the page in the Wiki, and link supporting repository paths as evidence. Keep authority and conflict handling consistent with this file and root `AGENTS.md`.

## Related Links

- [`README.md`](../../README.md) — source-repository entry point
- [GitHub Wiki remote](https://github.com/bannff/python-factory.wiki.git) — handbook remote
- [`docs/templates/`](../templates/) — artifact templates
