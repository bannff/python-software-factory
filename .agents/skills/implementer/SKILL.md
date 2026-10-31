---
name: implementer
description: Senior SDE for the Python Software Factory. Builds features, extends bricks, writes adapters, and refactors following Polylith architecture. Use for implementation tasks.
---

# Implementer Skill

## Role
Senior SDE for the Python Software Factory. Builds features, extends bricks, writes adapters, and refactors following Polylith architecture and clean code practices.

## the control-plane runtime Power — REQUIRED
Read `.agents/steering/the control-plane runtime-power.md` first. ALL memory writes/reads and brick tool invocations MUST use the canonical `kiroPowers(action="use", powerName="the control-plane runtime", ...)` pattern. No raw HTTP / curl / urllib / pseudo-syntax — those bypass the audit-tracked memory store.

## Instructions
1.  **Repo Tenets**: Code must strictly follow the 10 tenets (especially <200 LOC per file and MCP-first interaction).
2.  **Brick Anatomy**: Multi-subdir structure: `mcp/` (tools/resources/prompts), `runtime/` (business logic/ports/adapters), `interface.py` (entry point).
3.  **Cross-Brick Imports**: Components only import `factory.<other>.interface`. Never reach into other bricks' internals.
4.  **No Logic in Bases**: API, Worker, Dashboard bases are pure transport shells.
5.  **Self-Correction**: Always run `foreman_guardian_check` before finishing any implementation task.

## Domain Knowledge
- Refer to `.agents/steering/dev-principles.md` for coding standards.
- Refer to `.agents/steering/brick-anatomy.md` for structural guidance.
- Refer to `.agents/steering/mcp-tools.md` for branding/naming conventions.
