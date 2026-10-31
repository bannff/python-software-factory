# the control-plane runtime Onboarding — Orientation Map (updated 2026-10-03: Fresh orbit, strands flip #89, tracking route #80)

Onboarding artifact per `repo-onboarding` skill. Observations cited to file/line; inferences marked.

## Purpose

the control-plane runtime is the **control plane** of the Python Software Factory: a domain-agnostic
expert-augmentation engine that dynamically assembles bounded, objective-specific agent
teams through the `agent` brick's surfaces and invokes capability bricks through MCP.
It is **not** another agent runtime (normative: `.agents/steering/factory-protocol.md`,
"AGENTIC CONTROL PLANE"). Security is domain pack #1 — a *data pack* (skills/SOP/
taxonomy/challenge ground truth), not engine code (`.agents/steering/platform-doctrine.md`).
The single interaction surface is the control-plane runtime Web (Next.js cockpit).

The self-improving loop (North Star #3): agents act → games emit reward signals →
evals independently accept/promote evidence-bound trajectories → distillation (LoRA,
currently the keystone gap — trajectory landing-zone format unbuilt) → better model.

## Build / test / lint

| Action | Command |
|---|---|
| Sync env (workspace root) | `uv sync --frozen` (CI-exact) |
| Sync with test + ML groups (Darwin arm64) | `uv sync --group core-test --group ml --group can-test --config-settings-package lightgbm:cmake.define.USE_OPENMP=OFF` (the config-setting is the README "Darwin arm64 OpenMP Runtime Contract" — without it LightGBM fails to build here) |
| Add CAN test deps | append `--group can-test` |
| Run agent-brick tests | `MCP_LOCAL_AUTH=true MCP_LOCAL_AUTH_TOKEN=<16+ chars> MCP_PERMISSIONS_CONFIG_DIR=config/mcp_permissions WORKFLOW_CONFIG_DIR=projects/the control-plane project/config TELEMETRY_REQUIRED=0 uv run pytest components/agent/test -q` |
| Run one test | `uv run pytest projects/the control-plane project/test/test_main_composition_root.py -q` (same env vars) |
| Strict full suite (manual CI) | `uv run pytest` |
| CI (authority): PR lane | `.github/workflows/ci.yml` — `core-tests` job: `uv lock --check && uv sync --frozen --group langgraph-legacy` + `config/core-test-requirements.txt`; sanitizer dry-run + guardian ratchet (`checks`); strict suites (`CORE_SUITES`: components/test, foreman, agent, blockchain, events, workflow, scripts CI-lock/drift) + changed-brick selector |
| CI: ml-static lane | `uv run pytest components/machine_learning/test -q (… -k "properties or property or contract or registry or split or curriculum or projection")` + pyright ratchet (PR events) |
| CI: removed lanes (2026-10-18) | `can-tests` and `langgraph-legacy` were **deleted from `ci.yml` by owner decision** (CI minute cost). Consequences: the CAN/MF4/DBC dataset suite and the dormant-LangChain dormancy check no longer run in CI. Run them locally when touching those areas — `uv sync --frozen --group can-test && uv run pytest components/dataset/test`, and `uv sync --frozen --group langgraph-legacy --group core-test && AGENT_RUNTIME_ADAPTER=langchain uv run pytest components/agent/test -q` before flipping back to the dormant route. The `can-tests` entry was also removed from the `main-pr-gate` ruleset's required status checks. |
| CI does NOT run most of | `components/machine_learning/test` (only a `-k`-selected subset + pyright ratchet) and the heavy `projects/the control-plane project/test/*` suites (LNN/Chronos/LightGBM restart acceptance, mesh demos) — local-only (core-tests ignores `machine_learning/test` and `dataset/test` at collection) |
| CI: Frontend lane | `frontend-tests` job: shared-renderer `npm ci` → clean build/test → untracked-lib guard; next-dashboard `npm ci` → build/test (runs on PR + scheduled post-merge, not push) |
| Local dev stack | `./scripts/the control-plane runtime-ui.sh` (launcher exists; generates ephemeral `MCP_LOCAL_AUTH_TOKEN`, starts API :8000 + Next :3000, prints the dashboard URL) |
| Container stack | `make dev` / `make up` / `make sandbox-up` / `make deploy-challenges` / `make test` / `make build` (projects/the control-plane project/Makefile) |

**Dashboard dev origin (GH #142) — open `http://localhost:3000`, not a LAN IP.**
Next's dev server rejects `_next/*` and the HMR websocket for any host outside
its `allowedDevOrigins` allowlist; `next.config.ts` adds the loopback aliases
`127.0.0.1` and `[::1]` to the built-in `localhost`. Any *other* origin (a LAN
IP, a custom hostname, a proxy) gets a page that never hydrates: server-rendered
HTML, composer stuck on "Connecting to tools…", zero `/mcp` requests, and no
*actionable* signal — the browser only logs its own repeated HMR-socket failure
(`WebSocket connection to 'ws://…/_next/hmr…' failed: net::ERR_INVALID_HTTP_RESPONSE`),
which names a URL rather than the cause. The dev-only watchdog
(`frontends/next-dashboard/lib/dev-hydration-watchdog.ts`) now reports that
state as a `[the control-plane runtime]` console error plus a banner naming the origin to use.
Browser and E2E drivers must use an allowed origin.

**Test env vars required locally** (from CI `core-tests` job env + `projects/the control-plane project/.env.example`):
`MCP_LOCAL_AUTH=true MCP_LOCAL_AUTH_TOKEN=<any> MCP_PERMISSIONS_CONFIG_DIR=config/mcp_permissions WORKFLOW_CONFIG_DIR=projects/the control-plane project/config FACTORY_AGENT_CONFIG_DIR=.storage/agent-config TELEMETRY_REQUIRED=0`

**Agent authoring gates (issue #137/#138/#139):** the single
`SUPER_AGENT_ENABLE_AUTHORING_TOOLS` blanket switch is deprecated in favour of one
variable per surface — `FACTORY_AGENT_AUTHORING_SKILLS` (add, delete),
`FACTORY_AGENT_AUTHORING_STEERING` (create, update, delete),
`FACTORY_AGENT_AUTHORING_AGENT_TEMPLATES` (create, delete, fork, reset),
`FACTORY_AGENT_AUTHORING_CONFIG` (read, write); each also accepts `all` / `none`.
Exact precedence per (surface, action), first match wins: (1) that surface's
variable when non-empty, (2) the legacy `SUPER_AGENT_ENABLE_AUTHORING_TOOLS` env
blanket switch, (3) `settings.authoring.enabled` — consulted ONLY while NO
per-surface variable is set at all, (4) deny. `settings.yaml` is writable through
the config surface itself, so letting the persisted switch participate per-surface
was a privilege-escalation path (a config-only grant could raise every other
surface); with any per-surface variable set, `settings` is not consulted at all and
the config surface refuses to persist `authoring.enabled: true`
(`authoring_gate_immutable`). So documented deployments are unchanged (legacy switch
still means "everything on"), and with nothing
set, authoring is off and only the read-only surface plus
`agent_authoring_capabilities` (per-action probe) is exposed. Writes land in
durable roots (`FACTORY_AGENT_CONFIG_DIR` / `_SKILLS_DIR` / `_STEERING_DIR`,
defaults `.storage/agent-{config,skills,steering}`) — see `.env.example`.

**CRITICAL env gotcha:** root `.venv` and `projects/the control-plane project` env are separate.
Plain `uv run` uses the ROOT env. `uv run --project projects/the control-plane project` tries to
resolve the full the control-plane project dependency set (torch, mlflow, lightgbm build — fails
on the OpenMP contract). After `uv sync --group ml --group can-test` at root, the
root env satisfies the control-plane project tests; run them with plain `uv run` + the env vars above.

## Top-level structure

| Path | Responsibility |
|---|---|
| `components/` | Polylith bricks (agent, workflow, dataset, games, evals, blockchain, memory, kb, graph, security, …). Each: `BRICK.yaml`, `runtime/` (logic), `mcp/` (tools), `interface.py` (public API) |
| `bases/` | Pure transport shells: `api` (FastAPI composition root), `mcp_server` (aggregator), `worker`, `blueprint` |
| `projects/the control-plane project/` | The deployable project: composition root `main.py`, brick wiring in `pyproject.toml [tool.polylith.bricks]` (~45 bricks), Dockerfiles, challenge packs |
| `projects/the control-plane project/skills/security/` | Security domain-pack SOP skills (recon-lead, SAST scanner/validator/consolidator, DAST tester, sandbox-setup) |
| `projects/the control-plane project/challenges/` | Security ground truth: VAMPI, DVWA, Juice Shop, IDOR warehouse, LocalStack IAM-privesc/SSRF-Lambda + `gt_entries.json` per challenge |
| `frontends/next-dashboard/` | the control-plane runtime Web cockpit: Next.js 15 + CopilotKit v2 chat sidebar + AG-UI SSE |
| `frontends/shared-renderer/` | Universal A2UI React renderer package (component-map, renderers-*) |
| `.kiro/steering/`, `.agents/steering/` | Normative doctrine + implementation steering |
| `BRICKS_INDEX.yaml` | Generated brick catalog (2174 lines; `foreman` maintains it) |
| `config/mcp_permissions/` | MCP permission policies (CI points `MCP_PERMISSIONS_CONFIG_DIR` here) |

## Entry points

| Entry | What it starts |
|---|---|
| `projects/the control-plane project/main.py` | Unified MCP + REST + SSE + AG-UI on :8000 via `factory.api.main.create_app`; sets `EAGER_LOAD=0`, progressive discovery, `MCP_SERVER_NAME=the control-plane runtime` |
| `bases/api/src/factory/api/main.py` | Canonical composition root; `create_app()` installs MCP-UI redaction then mounts REST adapter + MCP aggregator + AG-UI streaming route |
| `frontends/next-dashboard` | Next.js cockpit on :3000; MCP BFF route handlers proxy with server-only bearer token |
| `RUN_MODE=api/mcp/worker` | Docker image modes: unified server / standalone stdio MCP / SQS worker |

## Critical path (chat → tools)

1. Browser → CopilotKit v2 chat sidebar (`selfManagedAgents` local registration, bd:python-factory-sopw)
2. → Next BFF `/ag-ui/run` → AG-UI SSE stream → API `stream_chat` via `factory.agent.interface.get_chat_agent_stream` (CHAT_STREAMING-gated)
3. → `agent` brick **Strands runtime** (default, route flip GH #89, 2026-10-02: `components/agent/.../adapters/strands_chat.py` + `strands_runtime.py`) — strands-agents 1.56 / MCP v2 streamable HTTP. Dormant LangChain/LangGraph route selectable via `AGENT_RUNTIME_ADAPTER=langchain` (deps in `langgraph-legacy` group)
4. → platform tool invoker reaches MCP aggregator → capability bricks (curated tool set)
5. → persona selected via registry: `COMPANION_X_CHAT_AGENT_ID` (default `the control-plane runtime-default`, LOUD-FAIL on miss)
6. Durable sessions: strands `SessionManager` over `SqlSessionRepository` at `./.storage/strands-sessions.db` (backend-swappable via `storage.sql.backend`); dormant LangGraph checkpoints at `./.storage/agent-checkpoints.db`; sessions in `session` brick `./.storage/sessions.db`

Model factory: `components/agent/.../runtime/adapters/strands_model.py` (default) from
`llm_gateway.resolve_chat_profile()` — `openrouter/<vendor>/<model>` | `ollama/<model>` | bare Bedrock id. Secrets by env-var *name* only.

## Active areas (churn 2026-09-29 → 2026-10-02)

- **agent brick**: Strands route flip landed Sep 29–Oct 2 in four phases (phase 0+1 registration/chat parity, phase 2 sessions/fork/interrupt/steer, phase 3 route default flip + langgraph-legacy dormancy group + 200-LOC trims); surrounding fixes 1476bdfb (persona model inherit + squads health + chat project binding), b0164ad6 (402/401/429 error mapping).
- **machine_learning brick**: issue #80 phases 1–2 landed (env-driven tracker backend, MLflowClient repair d8f7a3c4, pin syncs, ml.training events on all training paths, CAN lifecycle receipts, finetuning→tracker bridge).
- **ui/shared-renderer**: 8a77db3e (JSON-string payload tolerance on paint tools), 26b264ee (Text color/size/align in both renderers).
- **CI**: 8d4bb054 added the `ml-static` pyright-ratchet lane; 64a844e8 the langgraph-legacy dormancy lane; ea6a80f3 strict/post-merge get the langgraph-legacy group.
- **graph brick**: b7e2a4b3 registered the edge domain pack for mesh workflow taxonomy (the control-plane project edge-lab mesh work).

History was **reset at import** (commit bf5c1b41 "Initial commit — the control-plane runtime (history reset;
imported from python-factory-archive@7a361be7)") — churn older than the reset is
invisible; treat hotspots as provisional.

## Conventions observed

- Polylith: logic in `runtime/`, MCP in `mcp/`, public API in `interface.py`; no cross-brick internal imports — use `factory.<brick>.interface`
- <200 LOC/file enforced by `foreman_guardian_check` (blocking PR ratchet, file_size_mode='ratchet')
- MCP tools: `@deterministic` / `@operational` / `@authoring` (gated); brick-name prefixes
- Hypothesis property tests required for stateful bricks (`.agents/steering/hypothesis-testing.md`)
- Issue tracking: GitHub Issues (bannff/python-factory) since 2026-09-29 — `bd` is deprecated (its local Dolt store was unreparable); no markdown TODOs
- Zero `if domain == ...` — domain packs are data; trinary polymorphic params + registry-overlay merge is the blessed mechanism
- Push protocol: `git pull --rebase && git push` (bd deprecated; issues live on GitHub)

## Baseline test state (this machine — RESOLVED 2026-10-02)

~~7 passed, 4 failed (2026-09-29)~~ — all four failures were the missing per-machine
`projects/the control-plane project/config/settings.yaml` + absent `.env`. Both provisioned;
with `uv sync --group core-test` + the CI env vars above, the agent-brick suite is
**940 passed, 1 xfailed, 0 failed** (see Unknowns for the resolved detail).
First-session checklist (below) now reflects the working command.

## Unknowns

- ~~`bd` local store needs init/repair~~ — RESOLVED (2026-09-29): issue tracking moved to GitHub Issues (bannff/python-factory); `bd` deprecated.
- ~~Exact provisioning for `projects/the control-plane project/config/settings.yaml`~~ — RESOLVED: per-machine file now provisioned on this checkout (workflow engine registry present).
- ~~`MCPError` in the two restart tests / baseline 7-of-11~~ — RESOLVED: `uv sync --group core-test` + provisioned config → agent-brick suite 940 passed (2026-10-02).
- ~~Whether `frontends/shared-renderer` is consumed via workspace deps~~ — file-dep (`file:../shared-renderer`); `npm install` in next-dashboard after renderer changes.
- Runtime truth is now **Strands** (GH #89 route flip, 2026-10-02). The dormant LangChain route remains selectable (`AGENT_RUNTIME_ADAPTER=langchain`, `langgraph-legacy` dependency-group) with a CI dormancy lane; deletion review at the retrospective (~1 quarter clean production).

## First-session checklist

```bash
# 0. Issues → GitHub (bannff/python-factory); bd is deprecated.

# 1. Env (Darwin arm64) — core-test group needed for agent-brick tests
uv sync --group core-test --group ml --group can-test \
  --config-settings-package lightgbm:cmake.define.USE_OPENMP=OFF

# 2. Project env files
cp projects/the control-plane project/.env.example projects/the control-plane project/.env
cp frontends/next-dashboard/.env.local.example frontends/next-dashboard/.env.local
# settings.yaml ships as example; the live file is provisioned per-machine
# (projects/*/config/ is gitignored).

# 3. Run
./scripts/the control-plane runtime-ui.sh          # API :8000 + dashboard :3000
MCP_LOCAL_AUTH=true MCP_LOCAL_AUTH_TOKEN=<any-16+chars> \
MCP_PERMISSIONS_CONFIG_DIR=config/mcp_permissions \
WORKFLOW_CONFIG_DIR=projects/the control-plane project/config TELEMETRY_REQUIRED=0 \
  uv run pytest components/agent/test -q   # 940 passed, 1 xfailed (2026-10-02)
```
