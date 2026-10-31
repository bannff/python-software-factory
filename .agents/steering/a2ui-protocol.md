---
inclusion: fileMatch
fileMatchPattern: "**/a2ui/**, **/a2ui_*.py, **/ag_ui_*.py, **/views.py, **/views_tabs.py"
---
# A2UI Protocol Layer

**A2UI = schema. AG-UI = wire. mcp-ui = third-party SDK. Five carriers.**

That is the entire mental model for chat-surface UI in this repo. A2UI is a
flat-component payload (`{components: [{id, type, props, parent?}], name?}`).
AG-UI v0.0.47 is the typed-event SSE wire. The
[`mcp-ui`](https://mcpui.dev/) protocol/SDK is now adopted alongside as
carrier #5 — A2UI keeps the typed catalog, mcp-ui handles arbitrary
HTML/SVG/RemoteDOM/external apps. Five carriers move payloads (or A2UI-shaped
state) from agents to the the control-plane runtime frontend; each carrier has exactly one
producer-side hop and one consumer-side hook.

> **Naming — two layers, no collision.** The historical squat is closed:
> the internal `McpUiAdapter` was renamed to `InlineHtmlRenderAdapter` under
> bd:python-factory-kxpnf (`adapter_type "mcp-ui" → "inline-html"`,
> `application/vnd.mcp-ui+json → application/vnd.factory.inline-html+json`),
> and the real [`@mcp-ui/client`](https://mcpui.dev/) SDK is installed
> (`@mcp-ui/[email protected]`, `mcp-ui-server>=1.0.0,<2.0.0`). The two layers
> coexist by design: **A2UI** is our own typed catalog (24 component types
> in `components.py`) for inline cards and canvas slots; **mcp-ui** is the
> arbitrary-content escape hatch (`inline_html` / `external_url` /
> `remote_dom`). Use "tool-result paint" or "carrier #1" for inline A2UI
> rendering; "UIResource paint" or "carrier #5" for mcp-ui.

## Version pins

These are the only versions the chat surface is verified against. Any bump is
a deliberate review event — if a dispatcher predicate or wire-format detail
changes, the five-carrier table below changes with it.

| Package | Version | Role |
|---|---|---|
| `@ag-ui/[email protected]` | 0.0.47 | Typed event types + `EventType` enum |
| `@ag-ui/[email protected]` | 0.0.47 | `HttpAgent` + `defaultApplyEvents` reducer (RFC 6902 STATE patches) |
| `@copilotkit/react-*@1.53.0` | 1.53.0 | v1 alias surface (`/v2` re-exports next) |
| `@copilotkitnext/[email protected]` | 1.53.0 | `CopilotRuntime`, `StateManager`, `processAgentResult` dispatcher |
| `@copilotkitnext/[email protected]` | 1.53.0 | `useAgent` / `useComponent` / `useFrontendTool` / `useDefaultRenderTool` / `useRenderActivityMessage` |
| `strands-agents[openai]==1.50.2` | 1.50.2 | Hooks/plugins, public MCP content mapper, and native Bedrock Mantle `/openai/v1` + token refresh |
| `strands-agents-tools==0.4.1` | 0.4.1 | `workflow` tool (multi-agent DAG) |
| `@mcp-ui/[email protected]` | 5.6.2 | Carrier #5 consumer — `<UIResourceRenderer>` mount (`frontends/next-dashboard/node_modules/@mcp-ui/client/dist/index.mjs`) |
| `mcp-ui-server>=1.0.0,<2.0.0` | 1.0.0 (internal `__version__` 5.2.0) | Carrier #5 producer-side primitive (`mcp_ui_server.create_ui_resource`) — Python first-party. Used by `ui_paint_uiresource` |

## The five carriers

Each row maps one delivery path through the chat surface. Cite
file:line. Anything not in this table does **not** move payloads on the chat
path today.

| # | Carrier | Producer | FE consumer | Use case |
|---|---|---|---|---|
| 1 | Successful `ToolResult.data` A2UI payload `{components: [...]}` | `ui_paint_chat` (free-form A2UI; `components/ui/src/factory/ui/mcp/paint_chat.py`, bd:python-factory-zg93f) · `ui_render_brick_view` (brick-declared views; `components/ui/src/factory/ui/mcp/render_brick_view.py`, bd-C) · any MCP tool whose successful `data` is a flat A2UI payload | wildcard `useDefaultRenderTool` → `WildcardRender.detectCarrier === "a2ui"` → `<InlineView>` (`frontends/next-dashboard/lib/copilotkit/tool-renderers.tsx:127-181`; `node_modules/@copilotkitnext/react/dist/hooks/use-default-render-tool.mjs:42-47`) | render-on-tool-call (already lit) |
| 2 | `STATE_SNAPSHOT` / `STATE_DELTA` `value` / `delta` | new `state_delta_plugin` (bd:python-factory-syh1, pending) → `ChatStreamEvent.StateDeltaEvent` → `ag_ui_mapper_chat._on_state_delta` | `useAgent({agentId}).agent.state` (`node_modules/@copilotkitnext/react/dist/hooks/use-agent.mjs:67-83`); `defaultApplyEvents` STATE_DELTA branch applies RFC 6902 patches via `fast-json-patch` against `agent.state` | canvas-tab paint |
| 3 | `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` `content` | ~~`multiagent_lifecycle` plugin~~ REMOVED with legacy executors (#105); producer returns with strands.multiagent migration (#107) → `ag_ui_mapper_activity.py` (bd:python-factory-6zyg, shipped) | `useRenderActivityMessage` (`node_modules/@copilotkitnext/react/dist/hooks/use-render-activity-message.mjs`) → typed transcript card | sub-agent watch-live transcript card |
| 4 | `useComponent`-shaped tool call | LLM emits a tool call with the registered name; `useComponent` is sugar over `useFrontendTool` (`node_modules/@copilotkitnext/react/dist/hooks/use-component.mjs:55-66`) | `processAgentResult` (`node_modules/@copilotkitnext/core/dist/index.mjs:780-1290`) routes the call to the FE handler, which renders typed React via `frontends/next-dashboard/lib/copilotkit/agent-components.tsx:29-58` | typed inline cards (3 registered: `mini_graph_preview`, `finding_card`, `eval_result`; agent-prompt teaching pending) |
| 5 | Successful `ToolResult.data` mcp-ui UIResource `{type:"resource", resource:{uri:"ui://...", mimeType, text\|blob}}` | `ui_paint_uiresource` (`components/ui/src/factory/ui/mcp/paint_uiresource.py`, bd:python-factory-v2dko, PR #602); upstream-forwarded UIResources via `FactoryMCPClient` (`components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py`, bd:python-factory-nmzlk) | wildcard `useDefaultRenderTool` → `WildcardRender.detectCarrier === "mcp-ui"` (`frontends/next-dashboard/lib/copilotkit/tool-renderers.tsx:184-210`) → `<McpUiFrame>` (`frontends/next-dashboard/components/chat/mcp-ui-frame.tsx`, bd:python-factory-eyahj, PR #606) → `<UIResourceRenderer>` (`@mcp-ui/[email protected]/dist/index.mjs:2762-2774`, mode dispatch by `mimeType`) | arbitrary HTML/SVG/D3 (`inline_html`); embedded remote apps (`external_url`); host-themed RemoteDOM (`remote_dom`) |

**Envelope boundary.** The v1 `ToolResult` is transport metadata, not a sixth
UI carrier. Callers must inspect `ok` and route only successful `data` to the
listed carrier consumer; failures have `data: null`. The A2UI and UIResource
objects inside `data` retain their canonical shapes unchanged—do not flatten
carrier fields onto the outer result or treat domain-negative carrier results
as transport failures.

> **Tool-name prefixing — chat path vs aggregator path (bd:python-factory-3hkqx).**
> Carriers #1 and #2 surface `ui` brick MCP tools to the LLM. The chat agent
> reaches the **FLAT view**
> (`bases/mcp_server/src/factory/mcp_server/runtime/flat_view.py`), which
> mounts each brick's FastMCP via `flat.mount(brick_mcp)` **without a
> namespace** — so brick-decorated names like `ui_render_brick_view` /
> `ui_paint_canvas` / `ui_get_views` keep their **single** `ui_` prefix
> on this transport. The **double-prefix form** (`ui_ui_render_brick_view`,
> `ui_ui_paint_canvas`, `ui_ui_get_views`) exists only on the **aggregator
> path** used by the dashboard HTTP gateway. When citing a tool name in
> docs, match the path you're describing — chat allowlists and the
> the control-plane runtime prompt use single-prefix; aggregator HTTP traces use
> double-prefix.

**Why CUSTOM is not a carrier.** `CUSTOM` was historically advertised as a
fifth carrier. It isn't — `_map_a2ui_output` in
`components/ui/src/factory/ui/runtime/ag_ui_mapper.py:124-128` has zero
producers, and `defaultApplyEvents` in `@ag-ui/client` does not route
`CUSTOM` events to canvas state. CUSTOM stays in the enum only for legacy
`convertToLegacyEvents` (`Exit` / `PredictState`) and unknown event types —
see "What's NOT supported" below. The real fifth carrier is mcp-ui (above).

**Carrier #5 — shipped.** EPIC bd:python-factory-lo1g9 landed the mcp-ui
SDK on the chat path through six child bds (`lo1g9.0`-`.5`). Producer
`ui_paint_uiresource` (PR #602, bd-v2dko) emits the spec-nested
`{type:"resource", resource:{uri:"ui://...", mimeType, text|blob}}`
envelope; `FactoryMCPClient` (PR #600, bd-nmzlk) preserves
`EmbeddedResource.uri+mimeType` through Strands' content-block flatten
for upstream-forwarded UIResources; the wildcard predicate multiplex
(PR #604, bd-r6kki) routes via `WildcardRender.detectCarrier`; consumer
`<McpUiFrame>` (PR #606, bd-eyahj) mounts `<UIResourceRenderer>` with a
sandbox override, Zod validator, origin allowlist, and CSP module; T9
logger redaction (PR #604, bd-0x2jq) scrubs UIResource bodies from
logs/OTel. Sunset trigger for the `FactoryMCPClient` shim (when upstream
Strands fixes the flatten on `MCPClient.map_mcp_content_to_tool_result_content`
and we bump the pin) lives in `.agents/steering/upstream-sdk-shims.md#active-upstream-prs-were-watching`. Round 8 walkthrough: `.agents/recipes/agent-driven-ui.md`.

## State-shape contract (carrier #2)

The canvas paint carrier writes one slot per canvas tab under a single top-
level `canvas` namespace on `agent.state`. Slots are flat keys, **not**
prefixed `_a2ui_` legacy fields — the legacy `_a2ui_graph` /
`_a2ui_timeline` / `_a2ui_findings` / `_a2ui_canvas` vocabulary is dropped.

```jsonc
{
  "canvas": {
    "graph":     { "components": [...], "name": "graph"     },
    "timeline":  { "components": [...], "name": "timeline"  },
    "findings":  { "components": [...], "name": "findings"  },
    "live":      { "components": [...], "name": "live"      }
  }
}
```

`<slot>` ∈ `{graph, timeline, findings, live}`. Slot value is a normal
A2UI payload `{components: [...], name?: string}` — the same shape as
carrier #1 tool results, so the same `<InlineView>` renderer can surface
the slot in any canvas tab. (The fourth slot was renamed `canvas → live`
under bd:python-factory-3hkqx so the slot key matches the FE view id;
old `target="canvas"` calls now return a structured error pointing to
`live`. Memory id `aca2e1d6-3662-41dd-b54b-676475d032da`.)

### JSON Patch (RFC 6902) discipline

`STATE_DELTA.delta: any[]` is a JSON Patch ops list. `defaultApplyEvents`
applies it via `fast-json-patch.applyPatch(state, delta, validate=true,
mutate=false)` (`@ag-ui/[email protected]/dist/index.mjs`).

- Use `replace` (not `add`) once a slot exists. `add` on an existing path
  is fine; `replace` on a missing parent is a `MISSING_PARENT` patch error
  and the FE silently console-warns "Failed to apply state patch" with no
  re-render.
- Seed `state.canvas = {}` once with `STATE_SNAPSHOT` at the start of a run
  before any `STATE_DELTA` writes a slot. `handleStateSnapshot`
  (`@copilotkitnext/[email protected]/dist/index.mjs:1226`) spreads
  `{...state, ...snapshot}`, so a snapshot replaces.
- Serialize patches per slot. Concurrent patches against the same path can
  drop on the floor — queue them in the producer plugin and emit serially.
- Patches are valid only **inside a run**, between `RUN_STARTED` and
  `RUN_FINISHED`. `StateManager` (`core/dist/index.mjs:1124-1290`) keys
  state by `(agentId, threadId, runId)` and only persists during the apply
  pipeline.

### Producer rule

The producer for `STATE_DELTA` is an **MCP tool** —
`ui_paint_canvas(target, payload)` — not an inline Strands tool. This
keeps the canvas-paint surface auditable on the same ChatStreamEvent
plumbing as the rest of the chat path; bd:python-factory-syh1 wires the
new `StateDeltaEvent` variant + `state_delta_plugin.py` mirroring
`ag_ui_bridge.py`. Producer plugins sniffing `AfterToolCallEvent.result`
MUST handle both `{content:[{text:"<json>"}]}` and `{content:[{json:<dict>}]}`
shapes — Strands' `MCPClient` maps `MCPTextContent → {text}`
(`strands/tools/mcp/mcp_client.py:884`); a `{json}`-only check goes wire-
silent (bd:python-factory-3hkqx, memory `484c110d-ef57-4280-8e8c-40647f292bbb`).
The `live` slot is the un-typed escape hatch for the Live tab (was
`canvas` before bd:python-factory-3hkqx, memory id `aca2e1d6-3662-41dd-b54b-676475d032da`),
and producers MUST emit components whose `type` is in the supported
catalog (`Card`, `Text`, ..., `FilterBar` — see "Supported Component
Types" below); unknown types are rejected by `ui_paint_canvas` with a
structured error so the agent self-corrects.

**`props.children` lift — canonical wire is flat siblings (bd:python-factory-3hkqx
round 3, memory `c2a3ecd0-4a88-4d68-a26b-b36c62da4d20`, meta-architect
verdict `cec79d55-7ff3-41c0-b583-781bc5d7d2b7`).** A2UI's canonical
wire shape is flat siblings with `parent: "<id>"` refs. The agent's
intuitive shape often nests children inside `props.children:[...]`.
Producers MUST normalize before wire emit — `ui_paint_canvas` does
this automatically via
`components/ui/src/factory/ui/mcp/paint_canvas_lift.py::lift_props_children`
(extracted from `paint_canvas.py` to keep both files <200 LOC).
Recursive: multi-level nesting collapses correctly. The FE consumer
(`frontends/next-dashboard/lib/copilotkit/a2ui-tree.ts::a2uiToReactAdapterNodes`,
called from `usePaintedComponents`) is defensive and accepts all
three shapes (top-level `children`, `parent:` refs, `props.children`),
drops orphan `parent:` refs, and never double-renders — but the wire
SHOULD be canonical for cross-snapshot/replay invariance and stable
snapshot-test asserts. Custom producers that build A2UI by hand and
bypass `ui_paint_canvas` MUST call `lift_props_children` themselves
or emit canonical flat-with-`parent:` directly.

**Object-arg ingress coercion — `payload: JsonObject`
(bd:python-factory-38veu).** Paint tools' object args
(`ui_paint_canvas` / `ui_paint_chat` `payload`) are typed as
`factory.mcp_utils.interface.JsonObject` (from
`factory.mcp_utils.coercion.py`), matching the `evals_record_run`
precedent: LLM transports that serialize nested object args as JSON
strings are auto-recovered (stringified JSON parsed at the DTO
boundary, byte-identical to the dict path); a malformed string fails
loudly at pydantic validation instead of a friendly fail() envelope.
Do not "fix" `ui_paint_uiresource`'s `body: str` — it is a string by
design.

## Carrier #5 — UIResource render

Carrier #5 is the mcp-ui escape hatch for content the A2UI catalog can't
express: arbitrary HTML/SVG/D3, embedded remote apps, or host-themed
RemoteDOM trees. The `@mcp-ui/[email protected]` SDK ships
`<UIResourceRenderer>` which dispatches by `mimeType` at
`@mcp-ui/[email protected]/dist/index.mjs:2762-2774`.

### Wire shape

Two shapes are accepted at the FE consumer:

- **Spec-nested (preferred, producer-side):**
  `{type:"resource", resource:{uri:"ui://...", mimeType, text|blob}}` —
  what `ui_paint_uiresource` emits.
- **Flat (consumer-side, post-flatten):**
  `{text|image, uri:"ui://...", mimeType:"..."}` — the shape Strands'
  `MCPClient.map_mcp_content_to_tool_result_content` produces after
  flattening upstream-forwarded `EmbeddedResource` blocks.
  `FactoryMCPClient` (bd-nmzlk) preserves `uri+mimeType` through this
  flatten so the consumer can still detect the UIResource.

`WildcardRender.detectCarrier` (`tool-renderers.tsx:184-210`) checks
the nested shape first, then the flat shape; either match returns
`"mcp-ui"` and routes to `<McpUiFrame>`.

### Three modes

| `mimeType` (canonical) | SDK mode | Producer use case |
|---|---|---|
| `text/html` (or `text/html;profile=mcp-app`) | `rawHtml` (iframe `srcdoc`) | `inline_html` — arbitrary HTML/SVG/D3 |
| `text/uri-list` | `externalUrl` (iframe `src`) | `external_url` — embed a remote app |
| `application/vnd.mcp-ui.remote-dom+javascript` (e.g. `…;framework=react`) | `remoteDom` (script + RemoteDOM bridge) | `remote_dom` — host-themed component tree |

**MimeType normalization.** SDK strict-equality at
`@mcp-ui/[email protected]/dist/index.mjs:21-22` rejects RFC 7231 params
on `text/html` + `text/uri-list`, so the consumer (`mcp-ui-validator.ts`)
strips params before forwarding the resource to `<UIResourceRenderer>` —
**except** `framework=react` on `application/vnd.mcp-ui.remote-dom+…`,
which is preserved because RemoteDOM dispatch needs the framework hint.

### Producer rule

Producers MUST emit a `ui://`-scheme URI — that's the carrier
discriminator on `detectCarrier`. The spec-nested
`{type:"resource", resource:{...}}` envelope is preferred; flat
`{text|image, uri, mimeType}` is accepted for upstream-forwarded
resources after `FactoryMCPClient` preservation. `ui_paint_uiresource`
emits the nested form; producers that go through Strands MCPClient
forwarding will reach the consumer in the flat form.

### Security-policy summary (bd:python-factory-eyahj)

Carrier #5 is the first time external/agent-emitted content reaches a
non-React-controlled DOM tree. Five layers enforce least-privilege —
`security-engineer` verdict `d580bfdd` (14-row STRIDE):

1. **Sandbox override.** `<McpUiFrame>` drops `allow-same-origin` from
   the SDK default `sandbox="allow-scripts allow-same-origin"` for
   `external_url` (SDK source `index.mjs:234`). Iframes get
   `sandbox="allow-scripts"` only.
2. **CSP default-deny.** `lib/security/csp.ts` (wired into `next.config.ts`)
   sets `default-src 'self'`, `frame-src 'self'`, `frame-ancestors 'self'`,
   COOP `same-origin`, COEP `credentialless`, plus `X-Frame-Options`,
   `Referrer-Policy`, and `Permissions-Policy`.
3. **postMessage validator.** Zod discriminated union over
   `tool|prompt|link|intent|notify` actions. `ALLOWED_IFRAME_TOOLS` is
   read-only (`graph_get_app_topology`, `kb_search`, `memory_retrieve`);
   `ALLOWED_IFRAME_INTENTS` are `navigate-canvas`, `focus-finding`,
   `expand-card`. Layered on top of the SDK's source-window equality
   check at `@mcp-ui/[email protected]/dist/index.mjs:175`.
4. **Origin allowlist UX** for `external_url` — first-time confirm with
   `this-thread` / `always` / `never` choices stored in `localStorage v1`.
5. **Logger redaction (T9, bd-0x2jq).** `MCPUIRedactionFilter` scrubs
   UIResource bodies from log records and OTel spans; replaces body with
   `{uri, mimeType, size, sha256}` for danger MIMEs. Wired into
   `bases/api/src/factory/api/main.create_app()` via
   `install_mcp_ui_redaction()`.

**CSP env-gating (bd:python-factory-f4gjq, qa verdict `e7f73978`,
retro security verdict `dd49f85b`).** `script-src` is env-gated in
`buildContentSecurityPolicy()` at
`frontends/next-dashboard/lib/security/csp.ts:88-90`: production
(`NODE_ENV === "production"`) stays strict — `'self' 'wasm-unsafe-eval'`
per verdict `d580bfdd` §3, unchanged. Development adds
`'unsafe-inline' 'unsafe-eval'` so Next.js App Router RSC streaming
chunks (`__next_f.push([1, "..."])`) and the React Refresh runtime
(`new Function()` in `@next/react-refresh-utils`) don't break React
hydration; `connect-src` is widened to `ws: http:` for HMR + the
absolute-URL `/health` poll. The dev escape hatch is bridge-fixed,
not the long-term answer — a future bd will land middleware-injected
per-request nonce + `'strict-dynamic'` (`csp.ts:54-56` TODO) so dev
matches prod without `'unsafe-inline' 'unsafe-eval'`.

## What's NOT supported on the chat path

These are the dead ends. They look like carriers on paper, they aren't on
the wire, and they'll be removed under EPIC `python-factory-iet5`:

- **CUSTOM-A2UI events.** No producer in any base or component emits
  `CUSTOM` with an A2UI payload, and `defaultApplyEvents`'s `CUSTOM`
  handler does not route to canvas state. Drop the prior claim that
  "CUSTOM carries A2UI payloads" — use the carrier table.
- **`agent.output.a2ui` event-bus events.** `_translate_event` in
  `components/ui/src/factory/ui/runtime/session_bridge.py:81-89`
  consumes them; nothing produces them.
- **SessionBridge + 5 session tools + `ui_start_session` decorative
  call** at `bases/api/src/factory/api/runtime/ag_ui_routes.py:106`.
  Orphan code. Scheduled for deletion under
  bd:python-factory-b4rc / EPIC bdG (see deprecation note on the
  Session Tools table below).

## MCP Tools (10 tools in ui brick)

### A2UI Tools (5)

These remain canonical for converting between A2UI flat payloads and
brick-declared `UIView` trees.

| Tool | Category | Description |
|------|----------|-------------|
| `ui_get_a2ui_component_catalog` | deterministic | List supported A2UI component types with props |
| `ui_validate_a2ui` | deterministic | Validate A2UI payload before rendering |
| `ui_render_a2ui` | operational | Render A2UI payload to native UI (htmx/react/json) |
| `ui_a2ui_to_view` | operational | Convert A2UI payload to native UIView (optionally save) |
| `ui_view_to_a2ui` | deterministic | Convert stored UIView back to A2UI format |

### Session Tools (5) — DEPRECATED, scheduled for deletion

> **Status.** SessionBridge + `PushChannel` + `_map_a2ui_output` + the 5
> tools below + `ui_start_session` call at `ag_ui_routes.py:106` are
> orphan code with no live producer / consumer pair (meta-architect
> verdict on bd:python-factory-NEW1, memory id
> `2dabeff1-eee0-47cc-9d98-1165ebc88e96`). Deletion lands under
> bd:python-factory-b4rc / EPIC bdG. Do not add new callers.

| Tool | Category | Description |
|------|----------|-------------|
| `ui_start_session` | operational | Start a live agent session (returns session_id + view_id for PushChannel) |
| `ui_end_session` | operational | End a session and clean up PushChannel subscriptions |
| `ui_list_sessions` | deterministic | List active live agent sessions |
| `ui_get_session_info` | deterministic | Get info about an active session |
| `ui_get_session_graph` | deterministic | Get accumulated node/edge graph data for session visualization |

## Supported Component Types (24)

| A2UI Type | Native Type | Description |
|-----------|-------------|-------------|
| Card | card | Container with optional title |
| Text | text | Text content with formatting (¹) |
| Button | button | Clickable action |
| Form | form | Form container for inputs |
| TextField | custom | Text input field |
| Select | custom | Dropdown selection |
| DatePicker | custom | Date input |
| TimePicker | custom | Time input |
| Image | image | Image display |
| List | list | List of items |
| Table | table | Data table |
| Chart | chart | Data visualization |
| Alert | alert | Notification message (¹) |
| Progress | progress | Progress indicator |
| Metric | metric | Single metric display |
| Divider | custom | Visual separator |
| Spacer | custom | Empty space |
| ItemList | item_list | Rich filterable list with per-item detail drill-down |
| StatusDot | status_dot | Threshold-based colored status indicator |
| TrendBadge | trend_badge | Direction arrow with percentage change |
| Sparkline | sparkline | Inline mini bar or line chart |
| DetailPanel | detail_panel | Animated expand/collapse detail container |
| FilterBar | filter_bar | Horizontal category filter pill strip |

> **(¹) Prop-alias contract (bd:python-factory-3hkqx round 4, memory `a765bbd0`; qa-tester verdict `487b3ec5`).**
> Two types accept aliased prop names because the catalog `required_props` value, the agent's emission, and the FE renderer read drifted three different ways and produced an empty Live tab. The renderer now coerces; producers SHOULD still emit the canonical name.
> - `Text` — canonical `text`; `content` and `value` accepted as aliases. Renderer reads `text ?? content ?? value`.
> - `Alert` — body via `description ?? message`; heading via `title ?? message`. `required_props` is empty; one of `message` / `description` / `title` SHOULD be supplied.
>
> Pinned by `frontends/next-dashboard/components/renderer/__tests__/renderers-prop-aliases.test.tsx` (19 cases, one per catalog type), so renderer/catalog drift on any other type fails the canary first.

## A2UI ↔ brick view interconversion

Brick views (`*_get_views()`) use the native `UIView` format (nested
component trees with `children` arrays). A2UI's canonical wire is flat
siblings with `parent: "<id>"` refs; nested `props.children` is
ACCEPTED at the producer boundary and lifted to canonical form by
`paint_canvas_lift.py::lift_props_children` (see Producer rule
above) before wire emit. Both formats are interconvertible via
`ui_a2ui_to_view` / `ui_view_to_a2ui`.

Internally, A2UI is also a transparent protocol layer wrapping every
styling adapter (HTMX, React, Flet, JSON). In `view_manager.py`, primary
adapter names resolve to A2UI-wrapped versions (`htmx → A2UIAdapter(HTMXAdapter())`
etc.); `render_view(view_id, adapter="htmx")` already goes through A2UI.
This is orthogonal to the chat-surface carriers above — it's the
internal-rendering use of A2UI inside the dashboard pipeline.

## Chat-stream → AG-UI translation table

`ag_ui_mapper_chat.py` translates `ChatStreamEvent`s into AG-UI events.
Tool-call lifecycle and reasoning lifecycle are detailed below — they
deserve their own sections because the wire format requires bracketing
events, not single bloated events.

| `ChatStreamEvent.type` | AG-UI event(s) emitted |
|---|---|
| `text_delta` (new msg) | `TEXT_MESSAGE_START` + `TEXT_MESSAGE_CONTENT` |
| `text_delta` (same msg) | `TEXT_MESSAGE_CONTENT` |
| `tool_call_delta` (first) | `TOOL_CALL_START` |
| `tool_call_delta` (with `args_delta`) | `TOOL_CALL_ARGS` |
| `tool_result` | `TOOL_CALL_END` **then** `TOOL_CALL_RESULT` (canonical pair) |
| `reasoning_text` (first chunk) | `REASONING_MESSAGE_START` + `REASONING_MESSAGE_CONTENT` |
| `reasoning_text` (subsequent) | `REASONING_MESSAGE_CONTENT` |
| `step_start` / `step_finish` | `STEP_STARTED` / `STEP_FINISHED` |
| `done` | finalize: synthesize END+RESULT for unclosed tcids; close open reasoning + text |
| `error` | finalize as above + `RUN_ERROR` |

### Tool-call lifecycle: the END + RESULT pair (AG-UI v0.0.47)

A single `tool_result` from upstream emits **two** AG-UI events, in this
order — END first to close the span, then RESULT to materialize the
`role:"tool"` message:

```python
# 1. Bare close (no `result` field — bloating END violates the spec)
{"type": "TOOL_CALL_END", "toolCallId": "<tcid>", "timestamp": ...}

# 2. Result carrier
{"type": "TOOL_CALL_RESULT",
 "messageId":  "<fresh uuid4>",   # NOT the toolCallId
 "toolCallId": "<tcid>",
 "content":    "<json-stringified payload>",
 "role":       "tool",
 "timestamp":  ...}
```

`verifyEvents` in `@ag-ui/client` requires every open tool span to be
closed by `TOOL_CALL_END` before `RUN_FINISHED`. `TOOL_CALL_RESULT` is
not ledger-tracked and cannot close the span on its own. CopilotKit's
`useRenderToolCall` flips the pill `InProgress → Complete` only when it
sees the `role:"tool"` message synthesized from RESULT — END alone
leaves the pill spinning (bd:python-factory-3uhr's "endless spinner").

**Finalize synthesis.** `_synth_unclosed_tool_ends` (called on `done` /
`error`) emits the same canonical pair for any tcids opened with
`TOOL_CALL_START` but never closed via `tool_result` — defence in depth
against swarm/graph runners that return without an explicit tool-result
event. Synthesized `content` is
`{"status": "incomplete", "reason": "stream_finalized"}`. Invariant 6
in `_ag_ui_mapper_invariants` pins the END→RESULT order per tcid.

### Reasoning lifecycle: the START / CONTENT / END trio (bd:python-factory-eyuj)

`ChatStreamEvent.reasoning_text` chunks emit the canonical AG-UI trio.
CopilotKit's `CopilotChatReasoningMessage` auto-renders it as the
"Thinking" panel — no custom plumbing required FE-side.

```python
# 1. Open on first chunk (fresh uuid4 messageId)
{"type": "REASONING_MESSAGE_START", "messageId": "<uuid4>",
 "role": "assistant", "timestamp": ...}
# 2. Stream chunks (delta, like TEXT_MESSAGE_CONTENT)
{"type": "REASONING_MESSAGE_CONTENT", "messageId": "<same uuid4>",
 "delta": "<chunk>", "timestamp": ...}
# 3. Close (mapper auto-emits)
{"type": "REASONING_MESSAGE_END", "messageId": "<same uuid4>",
 "timestamp": ...}
```

A reasoning block opens on the first `reasoning_text` chunk and closes
on the next non-reasoning event (`text_delta`, `tool_call_delta`,
`tool_result`, `done`, `error`). This is what makes Claude 4
interleaved-thinking render correctly — a think → tool_call → think →
text sequence emits two correctly-bracketed reasoning pairs around the
tool call, not one sprawling block. Mapper tracks the open block via
`AGUIStreamState.reasoning_message_id`; `_close_reasoning_if_open`
fires from every non-reasoning handler and from `_finalize`. Replaces
the legacy `STEP_STARTED("reasoning")` + `CUSTOM("reasoning_text")`
shape, which never had a matching close and surfaced as opaque CUSTOM.

**Upstream emission (bd:python-factory-tpfk).** The mapper trio is
necessary but not sufficient — Strands has to actually emit
`ReasoningTextStreamEvent`. Setting
`COMPANION_X_CHAT_THINKING_BUDGET` (int, Bedrock min 1024) on a
thinking-capable chat model (Sonnet 3.7+ / Opus 4+) makes the chat
adapter construct `BedrockModel` with
`additional_request_fields={"thinking": {"type": "enabled", "budget_tokens": N}}`,
so Bedrock streams reasoning back, Strands surfaces them, the mapper
translates them via the trio, and the v2 Thinking panel
(bd:python-factory-47sl) renders. Haiku / Nova / Llama / GLM5 / GPT-OSS
chat models are no-op. Invariant 7 enforces matched START/END, no
nesting, no CONTENT after END, ≤1 END per `messageId`. Canary
`test_canary_strands_reasoning_event_dict_shape` pins the upstream
`ReasoningTextStreamEvent.as_dict()` shape so a Strands rename fails
fast.

## Canvas-Aware Chat (bd-vw04 + bd-115z)

The the control-plane runtime chat sidebar is a two-way bridge with the workbench
canvas. The agent SEES what the user is looking at (bd-vw04) and can
DRIVE the canvas through CopilotKit v2 frontend tools (bd-115z). This
is FE-tool round-trip — orthogonal to canvas paint (carrier #2).

### `RunAgentInput.tools[]` and `context[]` (bd-115z + bd-vw04)

Until those bds landed, the AG-UI route silently dropped both fields.

- **`tools[]` (bd-115z)** — Each entry is validated against
  `FrontendToolSpec` (`components/agent/runtime/models.py`) by
  `parse_fe_tools` (`bases/api/runtime/ag_ui_input.py`), then forwarded
  to `ChatAgentPort.stream(thread_id, message, fe_tools=...)`. The chat
  adapter hands the list to `FrontendToolPlugin.attach`, which registers
  stub `_StubAgentTool`s on the per-Agent `ToolRegistry.dynamic_tools`
  for the turn (legitimate Strands API; see `dev-principles.md`
  SDK-First). The stub yields a deferred sentinel
  `{"_frontend_pending": true, "name": "<bare>", "args": {...}}` and
  sets `request_state["stop_event_loop"] = True`. AG-UI surfaces the
  call via the canonical `TOOL_CALL_END` + `TOOL_CALL_RESULT` pair,
  the FE handler runs locally, and CopilotKit re-POSTs `/ag-ui/run`
  with the full message history including the `role: "tool"` reply.
- **`context[]` (bd-vw04)** — Each `{description, value}` entry is
  prepended to the user message by `prefix_context` as a labelled
  block: `"Canvas context (system-supplied, FE-pushed):\n- <desc>: <val>\n…"`.
  The label is intentional — the LLM treats the block as context, not
  user input. `<CanvasContextBridge />` (FE) publishes `activeView`,
  `activeTabId`, `openTabs`, last-10 `recentTools` via CopilotKit v2's
  `useAgentContext` (renamed from v1's `useCopilotReadable`).

**FE tool names use `fe_` prefix** so they never collide with the ~650
MCP brick tools. `_StubAgentTool` enforces this on registration. The
seed tool ships as `fe_navigate_canvas`. Adding a new FE tool is
FE-only — `useFrontendTool` again with a new name, description, Zod
schema, handler. See `.agents/recipes/canvas-aware-chat.md` for the
end-to-end walkthrough.

## SSE endpoint

`POST /ag-ui/run` in the api base (`bases/api/src/factory/api/runtime/ag_ui_routes.py`).
Accepts `RunAgentInput` JSON, starts an agent session, runs `agent_reason`
(routes to the persistent chat agent by default, or the orchestrator for
explicit swarm/graph hints), maps results to AG-UI events, streams SSE.

## Code Locations

```
components/ui/src/factory/ui/
├── runtime/
│   ├── a2ui/                            # A2UI schema + flat↔tree conversion
│   │   ├── schema.py                    # A2UIComponent, A2UIPayload, validate_a2ui
│   │   ├── renderer.py                  # a2ui_to_ui_view, ui_view_to_a2ui
│   │   └── components.py                # COMPONENT_CATALOG (24 types)
│   ├── adapters/
│   │   ├── a2ui_adapter.py              # A2UIAdapter wrapper (internal rendering)
│   │   ├── ag_ui_adapter.py             # AGUIAdapter — RenderAdapter for AG-UI SSE
│   │   └── inline_html_adapter.py       # InlineHtmlRenderAdapter — A2UI → HTML envelope (renamed from mcpui_adapter.py / McpUiAdapter under bd:python-factory-kxpnf; adapter_type="inline-html"; content_type application/vnd.factory.inline-html+json)
│   ├── ag_ui_mapper.py                  # Pure event mapper (internal → AG-UI)
│   ├── ag_ui_mapper_chat.py             # ChatStreamEvent → AG-UI; END+RESULT pair, REASONING_MESSAGE trio
│   ├── ag_ui_mapper_activity.py         # Carrier #3: subagent.* ACTIVITY events
│   ├── session_bridge.py                # DEPRECATED — orphan; deletion under bd-b4rc
│   └── view_manager.py                  # Wires A2UI + AG-UI as adapters
└── mcp/
    ├── a2ui_tools.py                    # 5 A2UI tools
    ├── paint_chat.py                    # ui_paint_chat — free-form A2UI inline in chat (bd:python-factory-zg93f, carrier #1 producer)
    ├── paint_canvas.py                  # ui_paint_canvas — slot paint (carrier #2 producer)
    ├── paint_canvas_lift.py             # lift_props_children flat-sibling normalizer (shared by paint_chat + paint_canvas)
    ├── paint_uiresource.py              # ui_paint_uiresource — mcp-ui UIResource emit (bd:python-factory-v2dko, PR #602; carrier #5 producer; modes: inline_html / external_url / remote_dom)
    ├── render_brick_view.py             # ui_render_brick_view — brick views inline (bd-C, carrier #1 producer)
    └── session_tools.py                 # 5 session tools — DEPRECATED

components/agent/src/factory/agent/runtime/adapters/
├── strands_mcp_chat_filter.py           # Chat allowlist; _EXTRA includes ui_paint_uiresource (lo1g9.5)
└── strands_mcp_client_factory.py        # FactoryMCPClient — Strands MCPClient subclass that preserves EmbeddedResource.uri/mimeType through the content-block flatten (bd:python-factory-nmzlk; sunset on upstream #2251/#2370 + pin bump — see `.agents/steering/upstream-sdk-shims.md#active-upstream-prs-were-watching`)

bases/api/src/factory/api/
├── main.py                              # install_mcp_ui_redaction() wires MCPUIRedactionFilter (bd:python-factory-0x2jq, lo1g9.2 T9)
└── runtime/
    ├── ag_ui_routes.py                  # POST /ag-ui/run SSE endpoint
    └── ag_ui_input.py                   # parse_fe_tools, prefix_context (bd-vw04+115z)

frontends/next-dashboard/
├── lib/
│   ├── copilotkit/
│   │   ├── tool-renderers.tsx           # Carrier #1 + #5 wildcard hook; WildcardRender + detectCarrier (lo1g9.3, bd-r6kki, PR #604)
│   │   ├── agent-components.tsx         # Carrier #4 useComponent registrations
│   │   ├── canvas-context.tsx           # Carrier #2 sibling: useAgentContext push (bd-vw04)
│   │   └── frontend-tools.tsx           # FE-tool round-trip: useFrontendTool (bd-115z)
│   └── security/
│       └── csp.ts                       # CSP module (default-deny frame-src/default-src 'self'; COOP/COEP/Permissions/Referrer/X-Frame-Options); wired into next.config.ts (bd:python-factory-eyahj)
└── components/chat/
    ├── mcp-ui-frame.tsx                 # Carrier #5 consumer: <McpUiFrame> mounts <UIResourceRenderer>; sandbox override drops allow-same-origin (bd:python-factory-eyahj, PR #606)
    ├── mcp-ui-error-boundary.tsx        # Sibling of <InlineViewErrorBoundary>
    ├── mcp-ui-validator.ts              # Zod discriminated union (tool|prompt|link|intent|notify) + ALLOWED_IFRAME_TOOLS / ALLOWED_IFRAME_INTENTS + mimeType normalizer
    └── mcp-ui-origin-allowlist.tsx      # external_url confirm UX (this-thread/always/never), localStorage v1
```
