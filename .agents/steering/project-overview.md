# Python Software Factory

A Polylith monorepo built FOR AI agents. Every brick exposes a full MCP interface.

The normative Agent/the control-plane runtime/Workflow/Dataset/Evals ownership split is defined only in [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md). This file describes current implementation state.

GitHub is the development work-tracking plane: Issues for work, Discussions for clarification, Wiki for high-level docs, and the Project board for tracking. the control-plane runtime is the runtime control plane; it composes through Agent surfaces rather than owning another agent runtime.

## Architecture

```
python-factory/
├── components/     # Reusable logic bricks (polymorphic, adapter-based)
├── bases/          # Entry points — pure transport shells (api, worker, mcp_server, blueprint)
├── projects/       # Deployable artifacts (the control-plane project)
└── BRICKS_INDEX.yaml
```

Deployment infrastructure is out of scope for this repo: this workspace is the factory and its deployable projects, not the environment they run in.

The blueprint base's CDK *generation* capability (turning `infrastructure_spec()` dicts into CDK code) remains in python-factory — that's a factory feature, not deployment infra.

## Repo structural graph (for developing the factory itself)

`.agents/scripts/build-repo-graph.py` (stdlib-only, `ast`+`sqlite3`) indexes this
repo's own Python source (`components/`, `bases/`, `projects/`) into
`.agents/.repo-graph/graph.sqlite` — gitignored, regenerable, not committed.
This is distinct from the `graph` brick, which is a runtime capability for
products built ON this repo (RL findings, telemetry, entities) — it has no
awareness of the factory's own source code. Rebuild with `build`, then query
`find-symbol`, `find-importers`, or `find-callers` instead of a fresh grep
when scoping a refactor's blast radius. See the `repo-graph-query` skill for
usage patterns.


## Core Principles

1. **MCP-First**: Every brick MUST expose full MCP primitives (tools, resources, prompts). Agents interact through MCP, not direct imports.
2. **Polymorphic/Agnostic**: All bricks use adapter pattern via `runtime/ports.py` Protocol interfaces. No hardcoded backends.
3. **<200 LOC**: Files stay under 200 lines. Split into `mcp/`, `runtime/` subdirs.
4. **No Cross-Imports**: Components import only `factory.<other>.interface`, never internals.
5. **Clean Architecture**: Business logic in `runtime/`, MCP surface in `mcp/`, public API in `interface.py`.

## Reasoning & Chat Agent Routing

This section records current routing, subordinate to the normative ownership split. A registered Agent Graph owns bounded research/synthesis/revision within one attempt; Swarm is exploratory. Workflow—not the Agent orchestrator—owns durable cross-brick attempts, global budgets, retries, and stopping.

The `agent_reason` MCP tool is the primary entry point for agent reasoning:

- **Default path → persistent chat agent**: Simple messages route to a singleton `ChatAgentPort` (Strands or memory mock). The chat agent retains conversation history per `thread_id` and has access to a curated subset of MCP tools (filtered from 300+ to ~50 relevant tools via `companion/tools.py` using per-query semantic vector search (Neo4j HNSW) with static prefix-based fallback). The `StrandsMCPChatAgent` adapter (`runtime/adapters/strands_mcp_chat.py`) connects to the MCP aggregator via native Strands `MCPClient` over Streamable HTTP. A `tool_filters` callback (based on the same prefix allowlist from `companion/tools.py`) controls which tools the LLM sees. The LLM calls tools directly by name (e.g. `memory_store`, `graph_find_entities`) — there is no `call_mcp_tool` wrapper.
- **Explicit swarm/graph → current within-attempt Agent executors**: When `context.hints` contains `swarm_id` or `graph_id`, `agent_reason` currently dispatches directly to `SwarmExecutor` or `GraphExecutor` for bounded multi-agent execution inside one attempt. The `GraphExecutor` → `WorkflowExecutor` branch for legacy `kind: workflow` registrations is current-state migration debt, not durable orchestration ownership: the Workflow brick remains responsible for attempt state, cross-brick budgets, retries, cancellation, recovery, stopping, and terminal reasons.

### Chat-Turn Scoring → Recursive Learning Loop (bd:python-factory-pfvo9)

The MAIN chat turn is scored, so the recursive-learning loop closes for ordinary chat — not just security graph runs. The reward signal is no longer pinned to security findings; it flows through the domain-agnostic `learning` brick.

The write side mirrors `LearningRecallPlugin` (the read side). `WorkCompletedEmitterPlugin` (`components/agent/.../runtime/adapters/strands_work_completed.py`) hooks Strands `AfterInvocationEvent` and emits a neutral `chat.turn.completed` event carrying `run_id`, `agent_id` + input/output summaries (65_536-char truncation; identity rides the MCP call envelope) — it computes no reward itself. The events `chat_reward_dispatch` handler (`runtime/chat_turn_handler.py`, subscription `auto-reward-chat-turn.yaml`, id `auto-reward-on-chat-turn`) routes that through `learning_compute_reward` (the `llm-judge` source), and emits `reward.computed` only when a source produced a signal (abstained turns produce no reward spam). The persona id rides as `domain_class`, so the existing memory fan-out tags the stored learning `{agent_id}-learnings` — exactly what `LearningRecallPlugin` queries next turn. The chat loop closes: act → score → store → recall.

`learning_compute_reward` (@operational, `components/learning/`) iterates every registered `RewardSourcePort` and returns a strict v1 `ToolResult[ComputeRewardOutput]` with `signals[]`, authoritative `source_id`, signed `scalar`, `verdict`, bounded `reward_value`, `wallet_id`, `provenance`, `scoring`, and JSON-only `raw` evidence. It never branches on a domain literal. Four built-in sources are seeded in code (`runtime/runtime.py::get_runtime`): `gt-findings` (delegates to `games_process_workflow_rl`, preserving the pre-seam F1 reward math and valid GT blockchain amount override; abstains without a `graph_id`), `llm-judge` (scores work output via `evals_evaluate_multi`; abstains on trivial or malformed scores), `user-feedback` (maps explicit thumbs up/down), and `telemetry` (maps `tool_error_rate` to a signed penalty). Events consumers use the validated top-level reward fields; nested `raw` evidence cannot authorize a mint or wallet. See `.agents/steering/brick-inventory.md` (the `learning` row) for the full brick contract.

#### User-feedback reward path (bd:python-factory-pfvo9 S2, PR #631)

The FE chat thumbs are now a real reward path, not a dead-end memory write. `persistFeedback` (`frontends/next-dashboard/lib/copilotkit/chat-feedback.ts`) publishes a `chat.feedback` event via `events_publish` carrying {`verdict`, `agent_id`, `thread_id`, `message_id`}. The `chat_feedback_dispatch` handler (`components/events/.../runtime/chat_turn_handler.py::handle_chat_feedback`, subscription `auto-reward-chat-feedback.yaml`, id `auto-reward-on-chat-feedback`) routes the verdict through the learning `user-feedback` source with no `output_summary` (so `gt-findings` + `llm-judge` abstain and `user-feedback` is the sole signal), then emits `reward.computed`: **up** mints + stores a learning, **down** stores a PENALIZED learning (zero tokens, signed scalar). The persona id (`companion_x_agent_id`) rides as `domain_class`, so the memory fan-out tags the stored learning `{agent_id}-learnings` — recalled next turn by that persona via `LearningRecallPlugin`.

#### Signed scalar + F1 pollution guard

`RewardSignal.scalar` is signed `[-1, 1]` with `reward_value = max(0, scalar) * 100` (`runtime/models.py::RewardSignal.from_scalar`): a negative scalar (down-vote, tool failure) is preserved as learning signal but NEVER mints tokens (verdict `penalized`). The improvement + convergence handlers now ingest ONLY ground-truth F1 rewards (`source_id` in `{"", "gt-findings"}`) via `components/events/.../runtime/learning_handlers/_common.py::_is_gt_reward` — so quality (`llm-judge`), feedback and penalty (`user-feedback`) signals never pollute the `pipeline-f1` baselines/drift, and a negative scalar never enters trend math.

### Swarm Tool Injection

`create_mcp_client()` from `runtime/adapters/strands_mcp_graph.py` creates a native Strands `MCPClient` connected to the aggregator via in-memory transport (`mcp.shared.memory.create_client_server_memory_streams()`). Swarm and graph agents receive this MCPClient as their tool source — no HTTP round-trip, no subprocess, no port binding.

The MCPClient uses `tool_filters={"allowed": [predicate]}` to scope which tools the LLM sees. The predicate checks tool names against `SWARM_TOOL_ALLOWLIST` from `runtime/swarm_tools.py`. A cached variant `get_graph_mcp_client()` reuses clients by allowlist frozenset.

The Llama-4 Maverick parameter normalization workaround (`_normalize_params`) now lives in `plugins/maverick_normalizer.py` as a `BeforeToolCallEvent` Strands plugin (`MaverickInputNormalizer`). It unwraps `{"type": "string", "value": "actual"}` wrappers before tool execution. Attach only when the model contains "maverick".

The duplicate-parallel-tool clamp (`ParallelToolDedupPlugin`, `plugins/parallel_tool_dedup.py`) sits in the same plugin slot as `MaverickInputNormalizer` and `FrontendToolPlugin` and is always-on for the chat agent. It hooks `BeforeInvocationEvent` (clears the per-turn seen-set) and `BeforeToolCallEvent` (sets `cancel_tool` when `(name, JSON-canonical input)` repeats), so Sonnet's hedged duplicate `tool_use` blocks under `toolChoice={"auto":{}}` are suppressed transport-agnostically across BedrockModel / AnthropicModel / NovaModel / LlamaModel / OllamaModel. The model-config route is closed: Bedrock Converse has no `disable_parallel_tool_use` knob, the Strands `ToolChoice` union (`.venv/strands/types/tools.py:104-170`) is closed and ships no parallel-control field, and putting `tool_choice` in `additionalModelRequestFields` is rejected at runtime because it conflicts with `toolConfig.toolChoice` (Strands `bedrock.py:301,307`). bd:python-factory-ads4; strands-expert verdict `29dbd5b6` corrects prior `8da46474`, meta-architect APPROVE `8659e552`.

> **Note — `call_mcp_tool` is fully retired.** Both the chat agent (native MCPClient over Streamable HTTP) and swarm/graph agents (native MCPClient over in-memory transport) expose individual typed tools to the LLM. The old `call_mcp_tool` meta-tool wrapper no longer exists anywhere in the agent component, including all `registry/defaults_*.py` files.

Tool name matching in `companion/tools.py` (`_static_select`) and `aggregator._parse_tool_name` both handle two naming conventions:
- Underscore-style: `sandbox_provision`, `graph_find_entities`
- Dot-style: `sandbox.provision`, `sandbox.execute`

This means bricks that expose dot-notation tools (e.g. the sandbox brick) are correctly routed and selectable by swarm agents.

The `mcp_utils` service registry (`set_service`/`get_service`) bridges the gap between bases and components: the API base registers `tool_invoker` when the aggregator initializes, and the agent component consumes it without cross-importing.

## Canvas-Aware Chat (bd-vw04 + bd-115z)

The the control-plane runtime chat sidebar is now a two-way bridge with the workbench canvas. The agent SEES what the user is looking at (bd-vw04) and can DRIVE the canvas through CopilotKit v2 frontend tools (bd-115z). Together with the bd-eyuj / bd-47sl / bd-tpfk thinking trio, these close the canvas-aware chat loop. Canvas paint (agent → page) is the next milestone — see EPIC `python-factory-iet5` "Agent Driven UI" (children bds A/G/C/I/D/E/F/B/H/J).

### Push: canvas → agent context (bd-vw04, FE-only)

`<CanvasContextBridge />` (`frontends/next-dashboard/lib/copilotkit/canvas-context.tsx`) calls CopilotKit v2's `useAgentContext` to publish a JSON-serializable summary of `activeView`, `activeTabId`, `openTabs`, and the last 10 `recentTools` on every turn. Workbench state was lifted to a React `<WorkbenchProvider>` mounted above `<CopilotKitProvider>` in `app/layout.tsx` so the bridge has access regardless of which canvas tab is focused.

CopilotKit forwards the published value as `RunAgentInput.context[]`. The api base (`bases/api/runtime/ag_ui_input.py::prefix_context`) prepends each `{description, value}` entry to the user message as a labelled block:

```
Canvas context (system-supplied, FE-pushed):
- the control-plane runtime canvas state: …: {"activeView": "graph", "activeTabId": "...", ...}

<original user message>
```

The label is intentional — the LLM treats the block as context, not as a user instruction.

### Pull: agent → canvas via FE tool round-trip (bd-115z)

`<FrontendTools />` (`frontends/next-dashboard/lib/copilotkit/frontend-tools.tsx`) registers `fe_navigate_canvas` via `useFrontendTool`. CopilotKit forwards every registration as `RunAgentInput.tools[]` with `frontend: true`. The api base validates each entry against the new `FrontendToolSpec` Pydantic model (`components/agent/runtime/models.py`) and threads them through to `ChatAgentPort.stream(thread_id, message, fe_tools=...)`.

The round-trip:

```
FE registers fe_navigate_canvas (useFrontendTool)
        │
        ▼
POST /ag-ui/run with tools[] + context[]
        │  (bases/api/runtime/ag_ui_routes.py + ag_ui_input.py)
        ▼
ChatAgentPort.stream(fe_tools=[FrontendToolSpec(...)])
        │
        ▼
FrontendToolPlugin.attach(fe_tools)
   BeforeInvocationEvent → ToolRegistry.register_dynamic_tool(_StubAgentTool)
        │
        ▼
LLM sees fe_navigate_canvas in tool list → emits tool_use
        │
        ▼
_StubAgentTool.stream() yields ToolResultEvent({_frontend_pending: true, name, args})
              + sets request_state["stop_event_loop"] = True
        │
        ▼
Strands ends the turn cleanly  (chat_stream finalize → AG-UI emits END+RESULT pair)
        │
        ▼
CopilotKit FE handler runs (workbench.switchView(view))
        │
        ▼
CopilotKit re-POSTs /ag-ui/run with full message history (incl. role:"tool" reply)
        │
        ▼
Strands resumes from the new tool message — normal continuation, no in-process await
```

### Strands SDK gap and the legitimate workaround

There is no per-invocation tool injection API in the installed Strands SDK — `BeforeModelCallEvent.tool_specs` is read-only. The legitimate path is `ToolRegistry.register_dynamic_tool` (`strands/tools/registry.py:583-595`); `dynamic_tools` is a per-Agent dict re-read on every model-prep call by `get_all_tools_config`. `FrontendToolPlugin` (`components/agent/src/factory/agent/plugins/frontend_tool_plugin.py`) registers stubs in `BeforeInvocationEvent` and strips them in `AfterInvocationEvent`. The plugin's docstring documents the gap and links the SDK source lines, per the SDK-First "build it but document the gap" clause in `dev-principles.md`.

The stub-tool pattern is deliberately narrow: yield exactly one `ToolResultEvent` with the deferred sentinel and set `stop_event_loop=True`. It does NOT raise (would surface as an error frame on the FE) and does NOT block (would deadlock the asyncio loop — the FE handler runs in a separate POST). CopilotKit v2's stateless re-POST is what closes the loop, not an in-process await.

### Naming and collision

FE tool names are namespaced with the `fe_` prefix so they never collide with the ~650 MCP brick tools the chat agent already sees through the in-process `MCPClient`. `_StubAgentTool` enforces this by wrapping any bare name on registration; the FE seed tool ships as `fe_navigate_canvas`.

Adding a new FE tool is FE-only: call `useFrontendTool` again with a new name, description, Zod schema, and handler — no Python change required. The handler interprets `parameters` opaquely; the api base only validates that each spec is a `FrontendToolSpec`-shaped object.

> **Naming note (CopilotKit v2):** `useCopilotReadable` was renamed to `useAgentContext` in v2. Older docs and recipes may still reference the v1 name; treat them as out-of-date.

See `.agents/recipes/canvas-aware-chat.md` for the end-to-end walkthrough, file map, and smoke tests.

### Inspector + Thinking-Panel Wiring (bd:python-factory-sopw)

Two FE-side fixes landed in the same session as the canvas-aware chat work to make the CopilotKit dev console (`<cpk-web-inspector>`, gated by `showDevConsole="auto"`) populate AG-UI Events / Agent / State after a chat run, and to make the Thinking panel render again on thinking-capable models.

#### `selfManagedAgents` over `runtimeUrl` (the anti-shadow rationale)

`<CopilotKitProvider>` (`frontends/next-dashboard/lib/copilotkit/provider.tsx`) registers `the control-plane project` locally via `selfManagedAgents={{ [COMPANION_X_AGENT_ID]: agent }}` and **does NOT pass `runtimeUrl`**. That combination is deliberate.

The shared agent identity lives in a single module — `frontends/next-dashboard/lib/copilotkit/companion-agent.ts` — which exports `COMPANION_X_AGENT_ID = "the control-plane project"` and a `createCompanionXAgent()` factory that returns a fresh `HttpAgent` bound to `/api/copilotkit/agent/the control-plane project/run` (the Hono runtime route). The BE runtime registration in `app/api/copilotkit/[[...path]]/route.ts` imports the same constant, so FE provider and BE runtime can never drift.

Why we don't pass `runtimeUrl` alongside `selfManagedAgents`: setting `runtimeUrl` triggers the async `/info` handshake which builds a `ProxiedCopilotRuntimeAgent` for `the control-plane project` and shadows the locally-registered `HttpAgent` via the merge order in `@copilotkitnext/core` `index.mjs::updateRuntimeConnection` — the spread `{...localAgents, ...remoteAgents}` lets the remote entry win. With both props set, `<CopilotChat>`'s `useAgent` and the dev inspector's `core.agents.the control-plane project` subscription end up bound to **different `HttpAgent` instances**, RxJS multicast can't fan events between them, and the inspector tabs stay empty after a successful chat run. Dropping `runtimeUrl` collapses both subscribers onto one `HttpAgent`. The runtime-status badge stays at "Disconnected" — that's cosmetic; there's no remote runtime to be connected to.

#### `<InspectorAttachWorkaround />` (upstream-gap workaround)

`frontends/next-dashboard/lib/copilotkit/inspector-attach-workaround.tsx` is a small idempotent companion mounted inside the provider tree. It polls for `<cpk-web-inspector>` after mount, then toggles `el.core = null; el.core = c` exactly once. This bridges an upstream `@copilotkitnext/[email protected]` gap where the inspector's `set core(value)` setter does not fire `attachToCore` on initial React-driven assignment, leaving the four inspector tabs unsubscribed. The toggle reliably re-runs `attachToCore(core)` → `processAgentsChanged(core.agents)` and wires the per-agent listeners. Per the SDK-First "build it AND document the gap" clause in `dev-principles.md`, this is a documented workaround scoped to the bug surface — not a bespoke wrapper — and is removable when the upstream patch ships.

#### Thinking-panel env (Strands → AG-UI → CopilotKit)

The `<CopilotChatReasoningMessage>` Thinking panel only renders when the API process is configured for extended thinking. Two env vars in `projects/the control-plane project/.env` gate the entire chain:

| Var | Purpose |
|-----|---------|
| `COMPANION_X_CHAT_MODEL` | Must be a thinking-capable Bedrock model (e.g. `us.anthropic.claude-sonnet-4-6`) for `reasoning_text` events to be emitted. |
| `COMPANION_X_CHAT_THINKING_BUDGET` | Bedrock minimum 1024; 16000 recommended. Unset / `0` makes `_thinking_budget()` return 0, which builds `BedrockModel` without `additionalModelRequestFields.thinking={...}`, so Sonnet emits no `reasoning_text`, so the AG-UI mapper has nothing to translate to `REASONING_MESSAGE_*`. |

Model capability matrix (chat works on all of these; the Thinking panel only lights up on the supported ones):

| Family | Thinking panel |
|--------|----------------|
| Anthropic Claude Sonnet 3.7+, Opus 4+ | ✅ supported |
| Anthropic Claude Haiku | ❌ no-op |
| Amazon Nova | ❌ no-op |
| Meta Llama (3.x / 4.x) | ❌ no-op |
| Z.AI GLM 5 | ❌ no-op |
| OpenAI GPT-OSS via Bedrock | ❌ no-op |

Both vars now have sane defaults in `projects/the control-plane project/.env` and `.env.example` so a fresh clone doesn't regress to an empty Thinking panel.

## Gateway Architecture

Bases (API, Worker, Blueprint, MCP Server) are pure transport shells. They depend ONLY on the
MCP aggregator (`mcp_server`), never on individual bricks. All brick logic is
accessed through MCP tool calls via the gateway bridge.

```
┌─────────────┐  ┌─────────────┐  ┌───────────────┐
│     API     │  │   Worker    │  │ Companion X   │
│  (FastAPI)  │  │  (Celery)   │  │(React/shadcn) │
└──────┬──────┘  └──────┬──────┘  └──────┬────────┘
       │                │                 │
       └────────┬───────┴─────────┬───────┘
                │   MCP Gateway   │
                │  (aggregator)   │
                └────────┬────────┘
       ┌─────────┬───────┼───────┬─────────┐
       │         │       │       │         │
    ┌──┴──┐  ┌──┴──┐ ┌──┴──┐ ┌──┴──┐  ┌──┴──┐
    │auth │  │ kb  │ │agent│ │event│  │ ... │
    └─────┘  └─────┘ └─────┘ └─────┘  └─────┘

                        API Base ◄── Companion X (HTTP/SSE)
```

Companion X (`frontends/next-dashboard/`) is a universal MCP-driven UI — any MCP client
(in-app agent, Kiro IDE, CLI tools, external agents) can drive actions, and the dashboard
renders whatever the MCP server produces. It lives outside the Polylith structure (not a
Python brick) and interprets ReactAdapter JSON to render shadcn/ui components in an IDE-like
workbench layout (ActivityBar | Canvas with tabbed views | collapsible ChatSidebar).
AG-UI SSE streams agent work into the chat sidebar; A2UI pushes rich views into the canvas.
Uses Next.js Route Handlers to proxy API requests, eliminating CORS without Python changes.

**Local dev runs with zero containers.** Bricks use lightweight adapters: ChromaDB for KB and memory (persists to disk), networkx for graph (ephemeral, CWE/OCSF taxonomy auto-seeds), SQLite for events, and in-memory adapters for cache/worker/storage. See `projects/the control-plane project/README.md` → "Local Dev (No Containers)" for the full adapter table.

### the control-plane runtime Local Boot Notes

For the lightweight local the control-plane runtime flow, source the project environment and
run the module through the editable workspace install. Hatchling exposes the
source roots explicitly listed in the root `[tool.hatch.build].dev-mode-dirs`
configuration; do not add a custom `PYTHONPATH`.

```bash
# Terminal 1 — API (from the repository root)
set -a
source projects/the control-plane project/.env
set +a
uv run python -m factory.api.main

# Terminal 2 — Next dashboard
cd frontends/next-dashboard
npm run dev
```

Local footguns verified on this machine:

- `projects/the control-plane project/.env` expects the API on `8000`, so the Next dashboard should use `API_URL=http://127.0.0.1:8000` in `frontends/next-dashboard/.env.local`.
- the control-plane runtime chat uses the Strands chat adapter and requires `COMPANION_X_CHAT_MODEL` plus the Python `ollama` package to construct `strands.models.ollama.OllamaModel`. If `ollama` is missing, chat can silently fall back to an AWS-style provider path and return credential errors even when Ollama is running.
- Local durable document storage now uses SQLite via `STORAGE_DOC_BACKEND=sqlite`, so telemetry/document persistence lands in `./.storage/docs.db` through `SQLiteDocumentStore`.
- Old TinyDB `JSONDecodeError` traces can still appear from stale shells or older processes that were started before the SQLite switch. For the current local the control-plane runtime env, the authoritative document store is SQLite, not `config/data/db.json`.

the control-plane runtime can also be deployed as an **AgentCore Runtime** (`RUN_MODE=agentcore`), where the MCP aggregator runs as a Streamable HTTP server on port 8000 using FastMCP's `stateless_http=True` mode. The AgentCore/cloud deployment uses persistent backends (Neo4j, DynamoDB, etc.) configured via env vars, so state lives in the database — not in process memory. AgentCore manages the container lifecycle and routes MCP protocol traffic to the server.

This means:
- Add a brick to BRICKS_INDEX → it instantly has backend, frontend, and worker capabilities
- Bases never need to change when bricks are added or removed
- Each base uses its natural transport (FastAPI/HTTP, MCP streaming, Celery/task); the active Next.js cockpit lives outside the Python base layer

### Progressive Discovery Meta-Tools (10 total)

The MCP gateway exposes 10 meta-tools for progressive brick discovery. Agents start with `list_bricks`, drill into a brick's tools/resources/prompts, then invoke them — all through the gateway, never direct imports. Nine tools use strict same-base Pydantic v2 DTO ingress and `ToolResult[OutputDTO]` egress. `call_brick_tool` also has strict DTO ingress but deliberately preserves its native FastMCP transport egress, avoiding an incompatible outer result envelope around the invoked tool's result or task payload.

| Meta-Tool | Category | Egress | Description |
|-----------|----------|--------|-------------|
| `get_capabilities` | deterministic | `ToolResult` | Machine-readable server capabilities |
| `health_check` | deterministic | `ToolResult` | Fast readiness probe for all bricks |
| `list_bricks` | deterministic | `ToolResult` | List available bricks with tool counts |
| `get_brick_tools` | deterministic | `ToolResult` | Get tool schemas for a specific brick |
| `get_brick_resources` | deterministic | `ToolResult` | Get resources and resource templates for a brick |
| `get_brick_prompts` | deterministic | `ToolResult` | Get prompt definitions for a brick |
| `get_tool_catalog` | deterministic | `ToolResult` | Eagerly load every brick and return the whole tool catalog; load failures appear in `bricks_failed` |
| `call_brick_tool` | operational | native transport | Invoke a tool on a specific brick. Accepts optional `envelope` JSON for principal context propagation and preserves the invoked tool's native envelope or task payload. |
| `read_brick_resource` | operational | `ToolResult` | Read a resource by URI from a brick |
| `render_brick_prompt` | operational | `ToolResult` | Render a prompt from a brick |

Implementation: `progressive.py` registers the nine `ToolResult` tools, `progressive_invocation.py` registers the sole native-transport exception, `tool_catalog.py` registers `get_tool_catalog`, and `aggregator.py` delegates. The legacy `server.py` module has been removed; this is the complete MCP-server contract.

### Tool Call Instrumentation

All tool invocations through the gateway are traced via OpenTelemetry spans. The `runtime/instrumentation.py` module wraps both async and sync tool calls with spans named `brick.tool.{brick}.{tool}`, recording `brick.name` and `tool.name` as span attributes. Errors set span status and record the exception.

The telemetry brick is force-loaded early in `create_server()` (before any tool calls) so the OTel SDK is initialized. If opentelemetry is not installed or the telemetry brick fails to load, tracing gracefully no-ops — no runtime impact.

### Envelope Context Propagation

Bases set per-request identity context so bricks can resolve the authenticated principal without explicit `user_id` parameters. Uses `contextvars` for async-safe, request-scoped propagation via `mcp_utils`.

1. **API base** (`bridge.py`): Extracts Bearer token → verifies via `auth_verify_access_token` → calls `set_envelope({"principal_id": ..., "tenant_id": ...})` before dispatching. Clears in `finally`.
2. **MCP protocol** (`progressive.py`): `call_brick_tool` accepts an optional `envelope` JSON string. MCP callers pass identity explicitly since there's no HTTP header. Same set/clear pattern.
3. **Bricks** read context via `get_principal_id()` from `factory.mcp_utils.interface` as a fallback when caller-supplied identity params are `None`.

Bricks don't need to know which transport delivered the request — `get_principal_id()` returns the right answer regardless.

## Brick-Declared Views (UI as Data)

Bricks with a UI surface declare views as **data**, not code. The rendering
pipeline is:

1. **Bricks declare** — `*_get_views()` tool returns component trees as plain dicts (using the `page` component type for standardized 3-zone layout)
2. **ui brick renders** — ViewManager + polymorphic adapters (HTMX, React, JSON, Flet, etc.)
3. **Dashboard serves** — wraps rendered HTML in the page shell, handles routing (GET + POST at `/api/tools/{tool_name}`, POST at `/api/chat/{tool_name}` for chat components). Companion X (`frontends/next-dashboard/`) renders shadcn/ui React components from the same ReactAdapter JSON in an IDE-like workbench layout — ActivityBar (icon rail), Canvas (tabbed views: Welcome, Graph, Timeline, Findings, Evals, ML), and a collapsible, user-resizable ChatSidebar (440px default; drag the left edge to resize, clamped between 440px and 70% of viewport width, persisted in `localStorage` under `the control-plane runtime:chat-width`). The chat sidebar is built on **CopilotKit v2** (`<CopilotChat agentId="the control-plane project">`); `CopilotChatReasoningMessage` auto-renders the canonical AG-UI `REASONING_MESSAGE_*` trio as the Thinking panel, and `useRenderTool` / `useDefaultRenderTool` route through a shared `<ToolCallCard>` for uniform Kiro / VS Code-style status pills across instrumented and uninstrumented tools (bd:python-factory-47sl). AG-UI SSE streams agent work into the chat; A2UI pushes rich views into the canvas. Uses Magic UI animations and React Force Graph 3D visualization.

> **Chat-surface UI rendering.** The pipeline above is the dashboard's HTMX/React render path. For the **chat surface** (CopilotKit v2 sidebar + canvas tabs) the canonical mental model is "A2UI = schema, AG-UI = wire, four carriers" — see `.agents/steering/a2ui-protocol.md` for the carrier table, `state.canvas.<slot>` shape contract, and JSON Patch (RFC 6902) discipline for `STATE_DELTA`-driven canvas paint.

```python
# In a brick's mcp/views.py:
def kb_get_views() -> list[dict]:
    return [{
        "id": "kb-search",
        "name": "Knowledge Base",
        "brick": "kb",
        "components": [{
            "id": "kb-page",
            "type": "page",
            "props": {
                "title": "Knowledge Base",
                "subtitle": "Semantic search, ingest, and manage documents",
                "icon": "🔍",
                "gradient": "from-teal-500 to-cyan-600",
                "tooltip": "Vector-powered document store · polymorphic backends",
            },
            "children": [
                {"id": "kb-stat-docs", "type": "metric",
                 "props": {"zone": "info", "label": "Documents", "value": "0",
                           "icon": "document-text", "intent": "hero",
                           "data_tool": "kb_get_collection_stats",
                           "tooltip": "Total ingested documents"}},
                {"id": "kb-search-form", "type": "form",
                 "props": {"zone": "controls", "tool": "kb_search",
                           "submit_label": "Search",
                           "fields": [
                               {"name": "query", "type": "text",
                                "placeholder": "What are you looking for?",
                                "tooltip": "Natural language query"},
                               {"name": "limit", "type": "range",
                                "min": 1, "max": 50, "value": 10},
                           ]}},
                {"id": "kb-read-tabs", "type": "tabs",
                 "props": {"tabs": [
                     {"id": "results", "label": "Results",
                      "tool": "kb_search"},
                 ]}},
                {"id": "kb-actions", "type": "action_pane",
                 "props": {"actions": [
                     {"id": "ingest", "label": "Ingest Document",
                      "tool": "kb_ingest", "fields": [...]},
                 ], "default_action": "ingest"}},
            ],
        }],
        "metadata": {"nav_label": "Knowledge Base", "nav_order": 10},
    }]
```

Components reference tools by name (`"tool": "kb_search"`), not by URL.
The adapter resolves the tool name to a transport-appropriate action.
Supported component types: `page`, `text`, `form`, `table`, `metric`, `button`, `card`, `list`, `chart`, `alert`, `progress`, `image`, `hero`, `tabs`, `breadcrumbs`, `modal`, `toast`, `graph_viewer`, `chat`, `item_list`, `status_dot`, `trend_badge`, `sparkline`, `detail_panel`, `filter_bar`.

The `item_list` frame is the workhorse — it replaces hardcoded canvas panels with a single data declaration that handles filtering, per-item status dots, trend arrows, sparklines, and expand-to-detail. See `docs/design/beautiful-frames-architecture.md` for the full spec.

This is a superpower: the same view definition renders in HTMX, React, Flet, a CLI,
or any future adapter. Bricks don't know or care about the transport layer.

Beyond static view declarations, the ui brick also supports live session-driven rendering.
`SessionBridge` subscribes to agent events (via the events brick) and translates them into
`ViewUpdate` objects pushed through `PushChannel` in real time. This powers the the control-plane runtime
live agent UI — agents emit events during execution, and the UI updates incrementally without
polling. Session tools (`ui_start_session`, `ui_end_session`, etc.) manage the lifecycle.

### Icons

The ui brick ships a full [Heroicons](https://heroicons.com/) registry (324 outline 24x24 icons, MIT license).
Metric components accept an `icon` prop with either a legacy alias (`chart`, `list`, `document`, `users`, `default`)
or any Heroicons name (`shield-check`, `globe-alt`, `cpu-chip`, etc.). No CDN or JS runtime needed — icons are
rendered server-side as inline SVGs. Run `scripts/generate_heroicons.py` to regenerate if Heroicons releases new icons.

## Brick Contract

Every MCP-enabled brick MUST expose:
- `get_capabilities()` - Machine-readable feature list
- `health_check()` - Fast readiness probe
- `describe_config_schema()` - JSON schema for configuration

Plus full MCP primitives:
- **Resources**: Schemas, docs, live data (`brick://schemas/*`, `brick://docs/*`)
- **Prompts**: Guided workflows for common tasks
- **Tools**: Categorized as deterministic/operational/authoring

Bricks with a UI surface SHOULD also expose:
- `*_get_views()` - Returns UIView definitions as data (see Brick-Declared Views above)

## Tool Categories

Use decorators from `factory.mcp_utils.interface`:
- `@deterministic` - Pure, no side effects (queries, schemas)
- `@operational` - Stateful but idempotent (CRUD operations)
- `@authoring` - Security-gated config changes

## Adapter Pattern

All bricks with external dependencies use Protocol interfaces:

```python
# runtime/ports.py
class StoragePort(Protocol):
    def save(self, key: str, data: bytes) -> None: ...
    def load(self, key: str) -> bytes | None: ...

# runtime/adapters/memory.py, s3.py, etc.
```

Bricks support open-source backends (Redis, Neo4j, etc.) and AWS-managed backends. AWS adapters follow a single `aws.py` entry point with a `service` parameter selector that delegates to backend classes in a `backends/` subfolder. Each AWS adapter exposes `infrastructure_spec()` for structured resource requirements. All 13 AWS adapters are complete (#336): auth, cache, events, graph, logger, machine_learning, notification, payments, permissions, storage, telemetry, worker, workflow.

### CDK Generation (Phase 3, #336)

The blueprint base closes the loop from adapter declarations to deployable infrastructure. Every AWS adapter's `infrastructure_spec()` returns a structured dict describing what it needs. The blueprint base consumes these specs and generates a complete CDK L2 Python project:

```
infrastructure_spec() dicts → Normalizer → Resolver → CDK Renderer
```

Why this matters: bricks declare their infrastructure needs as data, not code. Adding a new AWS adapter automatically makes its resources available for CDK generation — no manual IaC authoring required. The normalizer handles 3 spec shapes (flat, CFN-style, list), the resolver detects VPC requirements and generates IAM policies, and a pipeline renderer generates CI/CD workflows with OIDC auth.

4 MCP tools support this workflow:
- `blueprint_generate_cdk` — Generate CDK project from specs (operational)
- `blueprint_generate_pipeline` — Generate CI/CD pipeline (operational)
- `blueprint_validate_specs` — Validate specs before generation (deterministic)
- `blueprint_list_supported_services` — List supported AWS services (deterministic)

## AWS Credentials

Refresh before starting work (boto3 caches creds at process start — MCP server must be restarted after refresh):


## Verification Commands

```bash
foreman_guardian_check                 # Import integrity + branch + LOC + BRICKS_INDEX
uv run pytest                          # Tests
```
