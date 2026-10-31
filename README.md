# Python Software Factory

**Composable, MCP-native building blocks for agentic software — and the control-plane runtime, the assistant cockpit built from them.**

Every capability in this repo is a *brick*: a self-contained Python package with a typed public interface and a full [MCP](https://modelcontextprotocol.io) tool surface. Agents drive bricks through MCP, never through imports. Pick the bricks you need, compose them into a project, and an agent can operate the whole thing.

- **50 components · 5 bases · 3 projects**, organised as a [Polylith](https://polylith.gitbook.io/polylith) monorepo (counts derive from `BRICKS_INDEX.yaml`).
- **the control-plane runtime** — the flagship project: a local-first AI cockpit with chat, sub-agents, autonomous goal loops, unified graph memory, a real terminal, schedules, skills, and artifacts. One Next.js frontend, one FastAPI backend, no containers required.
- **Agent runtime**: Strands Agents SDK over MCP v2 (LangChain/LangGraph dormant behind `AGENT_RUNTIME_ADAPTER=langchain` + the `langgraph-legacy` group), streamed to the UI through CopilotKit / AG-UI.
- **Built to be run by agents.** The repo ships its own governance MCP server (`foreman`), steering docs, and an execution ledger so an autonomous loop can build the next feature unattended.

> **Status.** the control-plane runtime is mid-way through absorbing the feature set of [KiroCrew](https://github.com/kirodotdev) as its acceptance list — 56 of 100 in-scope features live, 29 more scaffolded and awaiting live proof. Progress is tracked row-by-row in [`.kiro/specs/python-factory-bp34j-companion-crew-features/kirocrew-feature-map.md`](.kiro/specs/python-factory-bp34j-companion-crew-features/kirocrew-feature-map.md).

---

## Contents

- [Quickstart](#quickstart)
- [Architecture](#architecture)
- [the control-plane runtime](#the control-plane runtime)
- [MCP everywhere](#mcp-everywhere)
- [Working in the repo](#working-in-the-repo)
- [For agents](#for-agents)
- [Docs and governance](#docs-and-governance)
- [License](#license)

---

## Quickstart

**Prerequisites:** Python ≥ 3.11, [`uv`](https://github.com/astral-sh/uv), Node 20+, and an [OpenRouter](https://openrouter.ai) API key (any OpenAI-compatible endpoint, Ollama, or Bedrock also work — see `.env.example`).

```bash
git clone https://github.com/bannff/python-factory.git
cd python-factory
uv sync                                          # every brick lands on the path (editable)
cp projects/the control-plane project/.env.example projects/the control-plane project/.env
#   -> set OPENROUTER_API_KEY and OPENROUTER_MODEL in that file
(cd frontends/next-dashboard && npm install)
scripts/the control-plane runtime-ui.sh                        # API on :8000, UI on :3000
```

Open <http://localhost:3000>. The chat sidebar drives the whole app — ask it to create a persona, spawn sub-agents, schedule a job, or open the terminal.

Use the `localhost` spelling (or `127.0.0.1` / `[::1]`): a Next.js dev server
only hydrates pages served from the hosts in its `allowedDevOrigins` allowlist,
and any other origin leaves a page that looks rendered but never connects
([GH #142](https://github.com/bannff/python-factory-INTERNAL/issues/142)).

Default local storage is container-free: SQLite for documents and checkpoints, a networkx graph for memory + knowledge, files under `.storage/`. Docker (`docker-compose.yml`) is optional and only needed for the heavier adapters (Postgres, Redis, Neo4j, Keycloak).

Full configuration reference: [`projects/the control-plane project/README.md`](projects/the control-plane project/README.md).

---

## Architecture

```text
python-factory/
├── components/       50 bricks — one capability each (agent, memory, graph, workflow, evals,
│                     games, sandbox, terminal, scheduler, session, ui, …)
├── bases/            5 transport shells — api (REST+MCP), mcp_server, worker, blueprint, openarcade
├── projects/         deployable compositions — the control-plane project, openarcade, circuitron
├── frontends/
│   └── next-dashboard/   the control-plane runtime cockpit (Next.js 15 · React 19 · shadcn/ui · CopilotKit)
├── BRICKS_INDEX.yaml the registry: every brick, its adapters, its dependencies
└── .kiro/ .agents/   steering, specs, skills, and the execution ledger agents read every cycle
```

**Every brick has the same shape** (the `workflow` brick is the exemplar):

```text
components/<brick>/
├── BRICK.yaml                  name, adapters, dependencies
└── src/factory/<brick>/
    ├── interface.py            the public API — the ONLY thing other bricks may import
    ├── runtime/                business logic; ports.py declares the Protocol, adapters/ implement it
    └── mcp/                    the MCP tool surface: @deterministic · @operational · @authoring
```

**Rules that keep it composable:** no cross-brick imports (use `factory.<brick>.interface`), files under 200 lines, one responsibility per file, adapters behind ports so any backend can be swapped by env var. `foreman_guardian_check` enforces all of it.

**Control-plane split** (normative detail in [`.agents/steering/factory-protocol.md`](.agents/steering/factory-protocol.md)):

| Layer | Owns | Does not |
|---|---|---|
| **Agent** brick | the intelligent runtime — personas, skills, tools, strands graphs/agents, sub-agents | durable process history |
| **Workflow** brick | durable attempts, budgets, retries, goal loops | reasoning |
| **Capability** bricks | typed, bounded operations over MCP | planning |
| **Evals** brick | frozen policies, evidence-bound scoring, promotion | letting agents grade themselves |
| **Games** / **Learning** | reward signals and RL evolution | accepting artifacts |

Agents decide and compose; bricks execute and guarantee; Evals challenge; Workflow remembers.

---

## the control-plane runtime

The reference product, and the thing the factory exists to build. Everything the user can do, the assistant can do too.

| Area | What's there |
|---|---|
| **Chat & sessions** | Multi-thread chat with persona selection per thread, fork, rewind, regenerate, pinned messages, session folders and summaries, side chat, a registry-driven right-side panel |
| **Agent capabilities** | Personas (built-in + user-created, no restart), skills, steering, hooks, MCP connections, sub-agent spawn / swarm / graph pipelines |
| **Goal loops** | the control-plane runtime runs its own autonomous build loop through the Workflow brick — admit a goal, fire cycles, checkpoint, score, retry |
| **Memory** | Memory and Knowledge Base share **one networkx graph** with a local embedder; browse, correct, inspect *why* something was recalled, export/import |
| **Terminal** | A real PTY in a bottom dock — arbitrary commands, no allowlist theatre; a single owner-editable approval list is the only gate |
| **Schedules & task runner** | Cron and one-shot jobs, spec-driven autonomous task runs |
| **Artifacts** | Save, version, and publish agent-rendered UI and documents |
| **Developer** | Diagnostics hub: MCP pool health, live tool stream, localStorage inspector, logs, debug tools |

Design doctrine: the engine is domain-agnostic — a domain is data (persona + skills + taxonomy + game config), never an `if domain ==` branch. Views are declared by bricks and rendered by the frontend (A2UI payloads over the AG-UI wire). Details: [`.agents/steering/platform-doctrine.md`](.agents/steering/platform-doctrine.md), [`.agents/steering/a2ui-protocol.md`](.agents/steering/a2ui-protocol.md).

---

## MCP everywhere

The MCP surface *is* the API. Two servers ship in the repo:

| Server | Command | Purpose |
|---|---|---|
| **foreman** | `uv run python -m factory.foreman.server` | Governance and scaffolding: create bricks, run compliance, manage the index |
| **the control-plane runtime** | `uv run python -m factory.mcp_server.core` | Every composed brick's tools, with progressive discovery |

Progressive discovery keeps the surface small: the server exposes nine meta-tools until you ask for more.

```text
list_bricks                       -> what's registered (tools_count: -1 = not loaded yet)
get_brick_tools("memory")         -> lists AND lazy-loads one brick
call_brick_tool("memory", "memory_retrieve", '{"query": "...", "user_id": "..."}')
read_brick_resource("graph://schemas/taxonomy/security")
```

Scope the surface with `MCP_INCLUDE_BRICKS=agent,memory,workflow` — you get exactly those bricks' tools, nothing else. The running the control-plane runtime API also serves the same surface at `http://127.0.0.1:8000/mcp/` (bearer token from `.env`), so any MCP client can drive the live product.

Ready-made [Kiro](https://kiro.dev) power definitions for both servers are in [`.kiro/powers/`](.kiro/powers/).

---

## Working in the repo

| Task | Command |
|---|---|
| Install everything | `uv sync` |
| Run tests | `uv run pytest <path>` (targeted) · `uv run pytest` (all) |
| Frontend tests / types | `cd frontends/next-dashboard && npx vitest run` · `npx tsc --noEmit` |
| Compliance gate | `foreman_guardian_check` (MCP) or `uv run python -c "from factory.foreman.guardian import run_all_checks; print(run_all_checks())"` |
| Workspace overview | `uvx --from polylith-cli poly info` |
| New brick | `foreman_create_component` (MCP) — never by hand |
| Launch the control-plane runtime | `scripts/the control-plane runtime-ui.sh` (owner stack, :8000/:3000) · `API_PORT=18000 NEXT_PORT=13000 scripts/the control-plane runtime-ui.sh` (agent smoke stack) |

**Conventions**

- Branch: `feat/<issue>-…`, `fix/<issue>-…`, `chore/<issue>-…`. Open a PR with `Fixes #<issue>`; `main` is protected.
- **Delete the branch when the PR merges.** Squash merges leave old branches looking "ahead" forever; the only branch that should exist at rest is `main`.
- Run `foreman_guardian_check` before every commit that touches `components/` or `bases/`.
- Property-based tests (Hypothesis) are required for stateful bricks.
- Prefer the framework primitive over a bespoke wrapper — if Strands, LangGraph, or CopilotKit ships it, use it. If it genuinely doesn't, build it *and* document the gap.
- Labels: one `status:*`, one `type:*`, any `brick:*`, at most one `agent:*` — see [`docs/labels.md`](docs/labels.md).

---

## For agents

Start at [`.agents/README.md`](.agents/README.md), then [`.agents/steering/factory-protocol.md`](.agents/steering/factory-protocol.md) — the single normative authority for architecture and the control-plane split.

The repo is designed so an autonomous loop can run for days without a human:

- **Ledger:** `tasks.md` in the active spec folder is the state. Read its header first — *State*, *Highest-leverage next step*, *owner rulings*. Update it every cycle.
- **Acceptance list:** the feature map. A row is done only with a real end-to-end proof, never a mock-vs-mock review.
- **Gates:** design and code reviews go to an independent auditor persona, never your own.
- **Done means merged.** Committed-to-a-branch is not done. Open the PR, land it, delete the branch.
- **Never** touch the owner's `:8000/:3000` stack; smoke on `:18000/:13000` and tear it down.

Memory for agents lives in the `memory` brick (`memory_store` / `memory_retrieve` via MCP, always with a `user_id`). Issue tracking is GitHub Issues.

---

## Docs and governance

- **Handbook:** the [GitHub Wiki](https://github.com/bannff/python-factory/wiki) is canonical **only at the exact revision pinned in [`AGENTS.md`](AGENTS.md)**. A floating wiki page is navigation, not authority. Precedence: system/user instructions → executable repo state (code, CI, schemas) → the pinned handbook → host-specific compatibility files.
- **Specs:** `.kiro/specs/<name>/` — `requirements.md`, `design.md`, `tasks.md` per feature. The active one is the the control-plane runtime KiroCrew port.
- **Steering:** `.kiro/steering/` (auto-loaded) and `.agents/steering/` (deep references: brick anatomy, MCP tool taxonomy, testing, memory, UI protocol).
- **Templates:** start any new doc, issue, wiki page, or discussion from [`docs/templates/`](docs/templates/).
- **Deployment infra** (CDK stacks, pipelines) lives in a separate repo; this repo keeps only the CDK *generation* capability in the `blueprint` base.

---

## License

**Business Source License 1.1** — see [LICENSE](LICENSE). Free for personal, academic, and evaluation use; commercial or production use requires a separate license. Converts to Apache 2.0 on 2030-03-03.

---

*The Python counterpart to the Software Factory ecosystem — a repo built for agents to build.*

<!-- ci smoke: verifies the PR-only lanes -->
