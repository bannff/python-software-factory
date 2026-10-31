# Copilot Instructions — Python Software Factory

**Before planning or editing, read `.agents/steering/factory-protocol.md` in full.**
This file is a concise VS Code-visible wrapper; the Kiro steering doc is the single source of truth.

## Non-negotiable rules

1. **Read the steering doc first.** `.agents/steering/factory-protocol.md` is the operating manual.
2. **AI-DLC sequence.** For code/config/docs/test changes: `Factory Lead` → (`Factory Meta-Architect` + `Strands Expert` planning) → `Factory Implementer` → `Factory QA Tester`. Invoke `Factory Security Engineer` only for high-value security-sensitive work.
3. **Architecture.** Python Polylith; bricks in `components/` and `bases/`; projects in `projects/`; public API in `interface.py`; business logic in `runtime/`; no cross-component internal imports (use `factory.<brick>.interface`).
4. **File size.** Keep files under ~200 LOC; component files ~150 LOC.
5. **Issue tracking.** Use `bd` only. `bd ready --json`, `bd update <id> --claim`, `bd create "title" -p <0-4> --deps discovered-from:<id>`, `bd close <id> --reason "..."`. No markdown TODOs.
6. **Quality gate.** Run `foreman_guardian_check` (MCP) before finishing when code/config changed.
7. **Push mandate.** Work is not complete until `git pull --rebase && bd sync && git push` succeeds and `git status` shows "up to date with origin".
8. **Tooling.** Prefer `uv sync` / `uv run`. Run tests with `uv run pytest`.
9. **SDK-First.** Favor Strands/CopilotKit primitives over bespoke wrappers; cite dispatcher source path + version pin before wrapping third-party FE SDKs. SDK shims, sunset triggers, and dispatcher pins live in `.agents/steering/upstream-sdk-shims.md`.
