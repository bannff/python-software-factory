# Recipe: Agent-Driven UI (Five Carriers, End-to-End)

How the the control-plane runtime agent draws stuff through SDK-native CopilotKit, Strands,
AG-UI, and mcp-ui primitives. The five carriers cover inline A2UI, canvas
state, sub-agent activity, typed React components, and arbitrary UIResources.

> **Source of truth.** `.agents/steering/a2ui-protocol.md` is the canonical
> five-carrier model. This recipe is the integration playbook with concrete
> producer → wire → consumer citations and smoke commands.

> **Persona note (bd:python-factory-hadbi.1).** The "the control-plane runtime agent" referenced throughout this recipe is now an `AgentConfig` registration named `the control-plane runtime-default` (`components/agent/src/factory/agent/registry/defaults_companion_x.py`), resolved at chat-build time via the `COMPANION_X_CHAT_AGENT_ID` env var (default `the control-plane runtime-default`, LOUD-FAIL on miss). Its `system_prompt` is the verbatim original `COMPANION_X_PROMPT` from `runtime/companion/prompt.py`, so behavior is byte-identical to pre-pivot. Future personas register their own `AgentConfig` (with `system_prompt`, `model`, optional `skills`, `description`) and flip the env — no code change in the chat adapter or the five-carrier wiring. End-to-end walkthrough: `.agents/recipes/domain-agnostic-substrate.md`.

## The five carriers, condensed

Full table (with version pins) lives at `.agents/steering/a2ui-protocol.md`.
Recipe-level summary:

| # | Carrier | Producer | FE consumer | Use case |
|---|---|---|---|---|
| 1 | Tool result `{components: […]}` | any MCP tool (e.g. `ui_render_brick_view`) | `useDefaultRenderTool` wildcard → `<InlineView>` | render-on-tool-call |
| 2 | `STATE_SNAPSHOT` / `STATE_DELTA` | `ui_paint_canvas` MCP tool + `state_delta_plugin` | `useAgent().agent.state.canvas.<slot>` | canvas-tab paint |
| 3 | `ACTIVITY_SNAPSHOT` / `ACTIVITY_DELTA` | `multiagent_lifecycle` plugin → `ag_ui_mapper_activity` | `useRenderActivityMessage` | sub-agent watch-live |
| 4 | `useComponent`-shaped tool call | LLM emits a typed-card name | `useFrontendTool` handler synthesised by `useComponent` | typed inline cards |
| 5 | mcp-ui UIResource | `ui_paint_uiresource` or a forwarded `EmbeddedResource` preserved by `FactoryMCPClient` | `<McpUiFrame>` → `<UIResourceRenderer>` | arbitrary HTML, remote apps, or RemoteDOM |

## Carrier #1 — Tool-result paint

What the agent does: any MCP tool whose result is a flat A2UI payload `{components: [...], name?: string}` paints inline. The seed tool is `ui_render_brick_view(brick_name, view_id?)` (bd-C), which round-trips brick `*_get_views()` through `ui_view_to_a2ui` to that exact shape.

- Producer (Python): `components/ui/src/factory/ui/mcp/render_brick_view.py:46-49` (bd-C, memory `de074119-4b93-4398-ad59-d5779bc41f00`).
- Chat allowlist + prompt teaching: filter logic lives in `components/agent/src/factory/agent/runtime/adapters/strands_mcp_chat_filter.py` (carved out of the adapter under bd-3hkqx to keep the file under 200 LOC) — `_EXTRA = {ui_get_views, ui_render_brick_view, ui_paint_canvas}`. Single-prefix names are correct on the chat path: the chat agent reads from the FLAT view (`bases/mcp_server/src/factory/mcp_server/runtime/flat_view.py`), which mounts each brick's FastMCP via `flat.mount(brick_mcp)` WITHOUT a namespace, so `ui_render_brick_view` keeps its single `ui_` prefix. The double-prefix form (`ui_ui_*`) only exists on the aggregator path used by the dashboard HTTP gateway. Companion prompt block at `components/agent/src/factory/agent/runtime/companion/prompt.py:33-55` (bd-I, memory `c6d67f24-9eb6-4c74-98b3-1420e698ba12`); allowlist fix-up bd-3hkqx (strands-expert design `016965bd-cdc8-45cd-b2e3-99b7172e40d8`, implementer landing `a0d27dae-fb40-41d1-8a8c-cde63ae6e81a`). The filter also rejects raw `<brick>_get_views` so the agent picks `ui_render_brick_view` instead — `ui_get_views` (the meta-discovery tool) stays allowed.
- Consumer (FE): wildcard hook in `frontends/next-dashboard/lib/copilotkit/tool-renderers.tsx:60-90` (`useCatchAllRenderer` — calls `useDefaultRenderTool`; routes payloads with an array `components` key into `<InlineView>`).
- Sample agent dialog: user says "show me the evals dashboard" → agent calls `ui_render_brick_view("evals")` → wildcard hook detects `Array.isArray(parsed.components)` and renders the panel inline.
- Canary: `frontends/next-dashboard/lib/copilotkit/__tests__/dispatcher-canary.test.tsx` (predates this epic, bd-f2h9).

## Carrier #2 — Canvas paint (STATE_DELTA)

What the agent does: `ui_paint_canvas(target, payload, mode?)` against one of four slots `{graph, timeline, findings, live}`. The tool result is tagged with the `_a2ui_canvas` sentinel; downstream plumbing transforms that into AG-UI `STATE_*` events that mutate `agent.state.canvas.<target>`. The fourth slot was renamed `canvas → live` under bd:python-factory-3hkqx (strands-expert design `56d2c5b6-8157-46ea-a128-64f6876a987e`, implementer landing memory `aca2e1d6-3662-41dd-b54b-676475d032da`) so the slot key matches the FE Live view id; old `target="canvas"` calls return a structured error pointing to `live`.

### Pipeline

1. **Producer (MCP tool).** `components/ui/src/factory/ui/mcp/paint_canvas.py:51-119` (bd-D, memory `508f6e27-45f0-4616-930c-3b6a19d58466`). Validates `target ∈ {graph, timeline, findings, live}`, validates the A2UI payload via `validate_a2ui`, validates each `component.type` against `COMPONENT_CATALOG` (case- and underscore-insensitive — so `Card`, `card`, `item_list`, `ItemList` all resolve; unknown types are rejected with a structured error enumerating the catalog so the agent self-corrects), returns `{"_a2ui_canvas": {target, mode, payload}, "rendered": true, …}`. Other keys are human-readable UX; `_a2ui_canvas` is the wire signal.
2. **Plugin (Strands hook).** `components/agent/src/factory/agent/plugins/state_delta_plugin.py:75-150`. Registers `AfterToolCallEvent` callback; `_extract_a2ui_canvas` unwraps **both** `{content:[{json:<dict>}]}` and `{content:[{text:"<json>"}]}` MCP content blocks — Strands' `MCPClient` maps `MCPTextContent → {"text":"<json>"}` (`strands/tools/mcp/mcp_client.py:884`), so FastMCP's `ui_paint_canvas` dict return lands in the `{text}` shape in production; sibling `ag_ui_bridge._normalize_payload` already handled both shapes, the state plugin was the outlier (bd:python-factory-3hkqx, memory `484c110d-ef57-4280-8e8c-40647f292bbb`). On match, pushes `StateDeltaEvent(target, mode, payload)` onto the per-turn `asyncio.Queue` via `loop.call_soon_threadsafe` (same queue/loop slots that `ag_ui_bridge` uses; `attach`/`detach` are idempotent).
3. **Event variant.** `components/agent/src/factory/agent/runtime/models.py:130-148` — `StateDeltaEvent` Pydantic variant, added to the `ChatStreamEvent` discriminated union.
4. **Mapper.** `components/ui/src/factory/ui/runtime/ag_ui_mapper_chat_state.py:36-67` — `on_state_delta(event, state, close_reasoning)`. First paint of the run (or explicit `mode="snapshot"`) emits `STATE_SNAPSHOT` carrying `{canvas: {target: payload}}` so the FE sees `state.canvas` exist before any subsequent `replace`. Subsequent paints emit `STATE_DELTA` with `[{op: "replace", path: "/canvas/<target>", value: payload}]` (RFC 6902, never `add` on a missing parent). Wired into the chat mapper at `ag_ui_mapper_chat.py:195` via `_DISPATCH["state_delta"]`.
5. **Consumer (FE hook).** `frontends/next-dashboard/lib/hooks/use-copilot-state.ts:55-71` (bd-E, memory `c12aae17-7266-4010-a68a-25e9ea833370`) — `useCopilotCanvasState` calls `useAgent({agentId: COMPANION_X_AGENT_ID, updates: [UseAgentUpdate.OnStateChanged]})` and casts `agent.state` to `{canvas?: CanvasState} & Record<string, unknown>`.
6. **Consumer (canvas views).** Per-slot memo via `usePaintedComponents` in `frontends/next-dashboard/lib/copilotkit/a2ui-canvas-slots.ts:47-69` (bd-F, memory `237c9336-e966-46b3-8f19-22b5e78339f0`). Under bd:python-factory-3hkqx round 3 (memory `c2a3ecd0-4a88-4d68-a26b-b36c62da4d20`), the hook delegates the A2UI flat → ReactAdapterNode tree shape transform to `lib/copilotkit/a2ui-tree.ts::a2uiToReactAdapterNodes` — previously a cast (a lie), now a real transform that defensively handles all three child-shape variants (top-level `children`, canonical `parent:` refs, lifted `props.children`), drops orphan `parent:` refs, and never double-renders. Graph view also gets a best-effort `a2uiSlotToGraphData` transform at lines 67-105. `<LiveView>` is the un-typed escape hatch at `frontends/next-dashboard/components/canvas/live-view.tsx`, registered for `activeView === "live"` in `components/canvas/canvas.tsx:79`.

### State shape

Per `.agents/steering/a2ui-protocol.md` State-Shape Contract:

```jsonc
{
  "canvas": {
    "graph":    { "components": [...], "name": "graph"    },
    "timeline": { "components": [...], "name": "timeline" },
    "findings": { "components": [...], "name": "findings" },
    "live":     { "components": [...], "name": "live"     }
  }
}
```

RFC 6902 discipline: seed `state.canvas={}` once with `STATE_SNAPSHOT`, then `replace` per slot. `add` on a missing parent fails silently in `fast-json-patch.applyPatch`. Patches are valid only inside a run (between `RUN_STARTED` and `RUN_FINISHED`). Serialise patches per slot.

### Sample agent dialog

User says "paint a graph showing the user kiro-agent". Agent emits:

```json
{
  "name": "ui_paint_canvas",
  "arguments": {
    "target": "graph",
    "mode": "snapshot",
    "payload": {
      "name": "graph",
      "components": [
        {"id": "u1", "type": "graph_node",
         "props": {"label": "kiro-agent", "type": "User"}}
      ]
    }
  }
}
```

Wire order: `TOOL_CALL_END` + `TOOL_CALL_RESULT` (chat card lands first) **then** `STATE_SNAPSHOT` (canvas paints). The Graph canvas re-renders via `a2uiSlotToGraphData`.

### Canary

`frontends/next-dashboard/lib/copilotkit/__tests__/state-delta-canary.test.tsx` (bd-H, memory `9dc7566e-3de1-4f5b-a23c-cd6482a9fa4e`). Three cases:

- `STATE_SNAPSHOT` seeds `agent.state.canvas` verbatim.
- `STATE_DELTA replace` after a snapshot mutates the slot via RFC 6902.
- **Negative pin:** `STATE_DELTA` on a missing parent path leaves state unchanged (the dispatcher logs `"Failed to apply state patch"` and swallows).

## Carrier #3 — ACTIVITY (sub-agent watch-live)

Predates this epic; included for the four-carrier picture.

- **Producer REMOVED (#105):** `plugins/multiagent_lifecycle.py` (`SwarmLifecyclePlugin` / `GraphLifecyclePlugin`) was deleted with the legacy executors; swarm/graph spans no longer emit ACTIVITY events. Mapper and FE consumer remain; the producer is due to return with the strands.multiagent migration (#107).
- Mapper: `components/ui/src/factory/ui/runtime/ag_ui_mapper_activity.py` — snapshot-bookend (open on `tool_call_delta`, N `ACTIVITY_DELTA` on workflow events, close on `tool_result`).
- Consumer (FE): `frontends/next-dashboard/lib/copilotkit/subagent-activity-renderer.tsx` exports `swarmActivityRenderer` + `graphActivityRenderer`, registered via the `renderActivityMessages` prop in `lib/copilotkit/provider.tsx`. The dispatcher matches on `renderer.activityType === message.activityType` (predicate cited in the steering doc).

## Carrier #4 — useComponent typed cards

Three cards ship today, register-only:

- Producer: LLM emits a tool call with the registered name (`mini_graph_preview`, `finding_card`, `eval_result`).
- Consumer: `frontends/next-dashboard/lib/copilotkit/agent-components.tsx:27-58` calls `useComponent` for each. `useComponent` is sugar over `useFrontendTool` (`@copilotkitnext/[email protected]/dist/hooks/use-component.mjs:55-66`); CopilotKit's `useRenderToolCall` consumes from the `renderToolCalls` registry.
- Trigger taxonomy: `.agents/recipes/useComponent-trigger-taxonomy.md` (bd-B, memory `5ee9a3eb-b466-4a1a-aa7f-2dd105171385`) — when to summon vs. prefer prose vs. prefer a brick view. Prompt teaching at `components/agent/src/factory/agent/runtime/companion/prompt.py:56-78`.
- Canary: `frontends/next-dashboard/lib/copilotkit/__tests__/use-component-canary.test.tsx` — pins `useRenderToolCall` consumes the typed render fn with parsed Zod args.

## Plugin ordering — why the chat card lands before the canvas paint

**STALE (#105):** the plugin set below was removed with the legacy executor era — `build_chat_plugins` and `strands_mcp_chat.py` no longer exist. The chat-adapter plugin pipeline is due to return with the strands.multiagent migration (#107); re-derive the ordering then. The e2e ordering pin (`test_canvas_paint_e2e.py::test_paint_canvas_emits_tool_result_then_state_delta_in_order`) still holds.

## SDK gotchas

- **vitest strict-ESM exposed a real `@ag-ui/client` namespace import bug.** `import * as a from "fast-json-patch"` doesn't expose `applyPatch` (it lives on the default export only). Production CJS bundling hides it; vitest does not. Fix: CJS-resolution alias added to `frontends/next-dashboard/vitest.config.ts` under bd-H. Without the alias the `STATE_DELTA` test sees `"a.applyPatch is not a function"` and silently swallows the patch.
- **Strands has no per-invocation tool-injection or tool-result-interception API.** `state_delta_plugin` uses the same per-`Agent` slot pattern as `ag_ui_bridge` and `frontend_tool_plugin` — `_chat_stream_queue` / `_chat_stream_loop` set in `_stream_once` try/finally. Cited in the plugin module docstring per the SDK-First clause in `dev-principles.md`.
- **MCP content-block shape gap — `{text}` vs `{json}`.** Strands' `MCPClient` serialises `MCPTextContent` as `{"text": "<json string>"}` (`strands/tools/mcp/mcp_client.py:884`); FastMCP dict returns wrap this way, NOT as `{"json": <dict>}`. Producer plugins that sniff tool results for sentinels (`state_delta_plugin`, future canvas-paint plugins) MUST handle BOTH shapes — `ag_ui_bridge._normalize_payload` is the sibling precedent. A `{json}`-only check goes wire-silent in production (no `STATE_SNAPSHOT`, no canvas paint, no error). Pinned by `test_sentinel_inside_strands_tool_text_wrapper` in `components/agent/test/factory/agent/test_state_delta_plugin.py` (bd:python-factory-3hkqx, memory `484c110d-ef57-4280-8e8c-40647f292bbb`).
- **CopilotKit-core does NOT enforce `useFrontendTool` Zod schemas at runtime.** The Zod parameters are converted to JSON Schema once via `zodToJsonSchema` for tool advertisement (`@copilotkitnext/[email protected]/dist/index.mjs::createToolSchema`); `executeSpecificTool` (same bundle, lines 886-940) only does `JSON.parse` on `toolCall.function.arguments` and hands the result to `tool.handler` directly — there is no `tool.parameters.parse` or `safeParse`. Consequence: an FE handler is the first and only validator of its own input. `fe_navigate_canvas` now guards with `if (!VIEW_IDS.includes(view)) return {success:false, error:"unknown view ..."}` and `openTab` falls back to `label || viewId` so a malformed call can never produce a blank tab. New FE tools MUST validate inputs explicitly. Debugger evidence: `.scratch/bd-3hkqx-ux-bugs/VERDICT.md` (Bug C, lines 886-940 cite); strands-expert verdict `56d2c5b6-8157-46ea-a128-64f6876a987e`; implementer landing `aca2e1d6-3662-41dd-b54b-676475d032da`.
- **BE↔FE A2UI type-set parity is enforced at test time, not runtime (bd:python-factory-3hkqx round 3, memory `c2a3ecd0-4a88-4d68-a26b-b36c62da4d20`).** `components/ui/test/factory/ui/test_a2ui_catalog_parity.py` reads `frontends/next-dashboard/components/renderer/component-map.ts` as text, normalizes both sides via the same `_norm` rule (lowercase + strip underscores), and asserts every `_norm(COMPONENT_CATALOG key)` is present in the normalized FE keyset. Adding a BE catalog entry without an FE renderer fails this canary fast — drift never reaches a yellow "Unknown component" box at runtime. The FE side normalizes too: `component-map.ts` exposes `getRenderer(name)` (case- and underscore-insensitive lookup over `COMPONENT_MAP`), and `component-renderer.tsx:27-28` pivoted from exact-key `COMPONENT_MAP[key]` to `getRenderer(key) ?? FallbackComponent` so `Card`, `card`, `item_list`, `Item_List` all resolve to the same renderer. Mirrors `paint_canvas.py:_norm`. New `SpacerRenderer` + `DividerRenderer` ship in `renderers-layout.tsx`; the four form-input types (`DatePicker`/`Select`/`TextField`/`TimePicker`) currently fall through to `CustomRenderer` pending dedicated renderers (discovered-from follow-up bd to file).
- **Catalog `required_props` is teaching, not enforcement (bd:python-factory-3hkqx round 4, memory `a765bbd0`; qa-tester `487b3ec5`).** The catalog docstring is what the agent sees; the FE renderer is what actually paints. When the two drift, the slot renders to nothing — the round-4 empty-Live-tab bug. Two types ship aliased reads in `renderers-basic.tsx`: `TypographyRenderer` reads `text ?? content ?? value`, `AlertRenderer` reads `description ?? message` for body and `title ?? message` for heading. `renderers-prop-aliases.test.tsx` (19 cases) pins each catalog type's `required_props` value rendering visibly in the DOM. **Adding a new component type — match catalog `required_props` to the renderer's prop reads exactly, OR add the alias acceptance to the renderer plus the alias names to the catalog `optional_props`. Add a row to `renderers-prop-aliases.test.tsx` for the new type either way.** Resolves bd:python-factory-dv4bo (Text P0) and bd:python-factory-l6ypd (Alert P1).
- **`next/image` host allowlisting vs agent-emitted URLs (bd:python-factory-3hkqx round 5).** `ImageRenderer` (`frontends/next-dashboard/components/renderer/renderers-data.tsx`) uses plain `<img>` instead of `next/image` because the agent emits arbitrary external URLs (`picsum.photos`, `dicebear`, `data:` URIs) and `next/image` rejects any host not in `next.config.js` `images.remotePatterns` with a runtime error. Allowlisting every potential host the agent might pick is a losing game. Plain `<img>` accepts everything; we keep `loading="lazy"` + `decoding="async"` for perf. Pinned by `renderers-prop-aliases.test.tsx::"Image accepts arbitrary external hosts"`.
- **Decorative props (`props.style`, `props.className`) — pass-through wrapper (bd:python-factory-3hkqx round 6, memory `79f3b2b6` / qa-tester `e9deb353`).** Every A2UI renderer reads only its narrow named props (`title`/`text`/`message`/`label`/`className`); none honor `props.style`. The agent emits decorative styling for visuals like gradient backgrounds, neon borders, and color overrides — those used to drop on the floor and produce empty white Cards. `ComponentRenderer` (`frontends/next-dashboard/components/renderer/component-renderer.tsx`) now wraps rendered output in `<div style={...} className={...}>` when either decorative prop is present on the node. Wrap is conditional so unstyled nodes keep their original DOM shape — no layout regression on the existing carrier-#2 views. Pinned by `renderers-style-passthrough.test.tsx` (23 cases). Resolves bd:python-factory-0zdqf.

## Round 7 — Gap A unblock + Strands EmbeddedResource shim + namespace cleanup (EPIC `python-factory-7z6rm`)

Three bds shipped under one epic. The triggering question was Gap A from a debugger session: **chat had no free-form A2UI producer**. `ui_render_brick_view` (carrier #1, bd-C) only renders pre-declared brick views; `ui_paint_canvas` (carrier #2, bd-D) writes to canvas slots, not chat. The agent could ask in prose ("here's a graph, view in canvas") but couldn't paint a one-off custom card inline.

### HYBRID verdict (Path 1 NOW, Path 2 separate epic)

Two paths surfaced in design (`meta-architect` `d0cdb475` + `strands-expert` `293c185e` converged on HYBRID):

- **Path 1 — `ui_paint_chat`**: a free-form A2UI MCP tool sibling of `paint_canvas`, returning `{components, name}` directly so the existing wildcard `useDefaultRenderTool` paints it. Zero FE changes, zero SDK risk. **Ship NOW.**
- **Path 2 — Real `@mcp-ui/client` SDK adoption**: install `@mcp-ui/client`, add carrier #5, sandbox in iframes. Blocked behind a Strands gap (`MCPClient` flattens `EmbeddedResource.uri` + `mimeType`). **File as separate epic** bd:python-factory-lo1g9 gated on the Strands fix landing.

### What shipped

**bd:python-factory-zg93f — `ui_paint_chat` (carrier #1 producer; implementer `71749b2c`).**
Mirror of `ui_paint_canvas` minus the `_a2ui_canvas` sentinel. Uses the same `validate_a2ui` + `COMPONENT_CATALOG` allowlist + `lift_props_children` normalization — adding a new component type updates both producers automatically because the catalog is the single source of truth. Returns `{components, name}` directly so the FE wildcard predicate (`Array.isArray(parsed.components)`) at `frontends/next-dashboard/lib/copilotkit/tool-renderers.tsx:54-86` paints it via `<InlineView>`. Zero FE changes — the renderer already existed for any MCP tool returning A2UI shape. File: `components/ui/src/factory/ui/mcp/paint_chat.py` (~110 LOC, well under 200).

```python
# Sample agent dialog — user: "show me a stat card with our finding count"
ui_paint_chat(
  payload={
    "components": [
      {"id": "m1", "type": "Metric",
       "props": {"label": "Findings", "value": "42"}}
    ],
    "name": "Findings stat",
  }
)
# Wire: TOOL_CALL_END + TOOL_CALL_RESULT carrying {components, name};
# wildcard hook detects the components array; <InlineView> paints inline
# under the tool-call card. No STATE_DELTA; no canvas slot mutation.
```

**When to use which carrier-#1 producer:**
- `ui_paint_chat` — free-form, one-off custom visualization the agent designs on the fly. Stays in chat scrollback.
- `ui_render_brick_view` — pre-declared brick views (`*_get_views()`). Surfaces 21+ existing views without the agent designing layout. Stays in chat.
- `ui_paint_canvas` — full-canvas paint into one of `{graph, timeline, findings, live}` slots via `STATE_DELTA`. Persists across the run; survives chat scroll.

**bd:python-factory-nmzlk — `FactoryMCPClient` Strands subclass (strands-expert verdict `bcebadb4`).**
Strands 1.50.2's public `MCPClient.map_mcp_content_to_tool_result_content` flattens `EmbeddedResource` blocks irreversibly: `TextResourceContents` → `{"text"}` (uri+mime dropped); `BlobResourceContents` non-text/non-image (e.g. `application/vnd.mcp-ui.remote-dom+javascript`) → `None` (silent drop). Upstream issue [#2251](https://github.com/strands-agents/sdk-python/issues/2251) and merged PR [#2370](https://github.com/strands-agents/sdk-python/pull/2370) established the public extension point but did not fix the data loss. Local upstream behavior work is bd:python-factory-0g0gg.

`FactoryMCPClient` (`components/agent/src/factory/agent/runtime/adapters/strands_mcp_client_factory.py`) overrides exactly that one method, preserving `uri` + `mimeType` on every `EmbeddedResource` shape (text, image blob, text-like blob, unknown blob → placeholder). All other `MCPClient` behavior is inherited. The wire-shape extras (`uri`, `mimeType` on `ToolResultContent`) are ignored by Bedrock's `_format_request_message_content` (`strands/models/bedrock.py:633-661`) which dispatches on known-key presence, so the LLM-bound payload is unchanged.

**Sunset trigger.** Listed in `.agents/steering/upstream-sdk-shims.md#active-upstream-prs-were-watching`: when upstream lands a real fix and we bump the strands pin, delete `strands_mcp_client_factory.py`, delete `test_canary_strands_mcp_embedded_resource.py`, restore plain `MCPClient` import in `strands_mcp_graph.create_mcp_client`. Per the SDK-First "build it but document the gap" clause in `dev-principles.md`.

**bd:python-factory-kxpnf — `McpUiAdapter` → `InlineHtmlRenderAdapter` rename (refactorer `5c3de106`).**
Internal A2UI → HTML renderer that previously squatted the `mcp-ui` name. File `mcpui_adapter.py → inline_html_adapter.py`; class `McpUiAdapter → InlineHtmlRenderAdapter`; `adapter_type "mcp-ui" → "inline-html"`; content_type `application/vnd.mcp-ui+json → application/vnd.factory.inline-html+json`. Zero behavioral change — same HTML output, same `view_manager.py` wiring. Frees the `@mcp-ui` namespace for real SDK adoption under bd:python-factory-lo1g9.

### Phase 3 outlook — bd:python-factory-lo1g9 (real `@mcp-ui` adoption)

Separate epic, gated on Strands fix landing. Scope:
- Install `@mcp-ui/client` in `frontends/next-dashboard`.
- Wire a carrier-#5 mapper consuming `EmbeddedResource` blocks now preserved by `FactoryMCPClient` (production via `AfterToolCallEvent` hook reading off `agent.messages`).
- Render `ui://` URIs through `<UIResourceRenderer>` with iframe sandboxing.
- **`security-engineer` consult is mandatory** — iframe sandbox attributes, CSP for inline content, `postMessage` allowlist between sandbox and parent. Carrier #5 is the first time external/agent-emitted content reaches a non-React-controlled DOM tree.

When the epic lands: carrier table grows from four to five; `FactoryMCPClient` becomes the deletion candidate the moment upstream Strands fixes the flatten.

- **CUSTOM-A2UI events** — no producer in any base or component, and `defaultApplyEvents` doesn't route `CUSTOM` to canvas state.
- **`agent.output.a2ui` event-bus events** — consumer existed in the deleted `session_bridge.py`; no producers ever shipped.
- **SessionBridge + 5 session tools + `ui_start_session` / `ui_end_session`** — deleted under bd-G (memory `a6fc807b-0080-435b-8d32-5b9682eb313f`, −891 LOC).

## Round 8 — Carrier #5 mcp-ui SDK adoption (EPIC `python-factory-lo1g9`)

Round 7 filed `bd:python-factory-lo1g9` as a follow-up epic for real `@mcp-ui/client` adoption gated on the `FactoryMCPClient` Strands subclass landing. That epic shipped under six child bds (lo1g9.0 through lo1g9.5). The chat path now has a real fifth carrier — arbitrary HTML/SVG/D3, embedded remote apps, and host-themed RemoteDOM trees flow through `<UIResourceRenderer>` with sandboxing, CSP, postMessage validation, origin allowlist UX, and logger redaction.

### HYBRID verdict (revisited from Round 7)

The Round 7 design phase converged on HYBRID — `meta-architect` `d0cdb475` + `strands-expert` `293c185e` agreed: ship `ui_paint_chat` (carrier #1 expansion) immediately, file mcp-ui adoption (carrier #5) as a separate epic gated on the Strands gap. Once `FactoryMCPClient` (bd-nmzlk) closed that gap, `security-engineer` `d580bfdd` ran a 14-row STRIDE on the consumer surface and approved with the sandbox/CSP/postMessage policy now wired in lo1g9.4.

### What shipped

| bd | PR | Round | Landed |
|---|---|---|---|
| bd-8atx4 | #601 | lo1g9.0 | `InlineHtmlRenderAdapter` rename re-run (cleanup follow-up to bd-kxpnf; chart guards + InlineView ErrorBoundary) |
| bd-3h8e9 | #603 (`fd45e9dc`) | lo1g9.1 | Install `@mcp-ui/[email protected]` (npm exact pin) + `mcp-ui-server>=1.0.0,<2.0.0` (PyPI; internal `__version__ 5.2.0`); SDK presence canary |
| bd-0x2jq | #604 | lo1g9.2 (T9) | `MCPUIRedactionFilter` — strips UIResource bodies from log records and OTel spans for danger MIMEs (replaces body with `{uri, mimeType, size, sha256}`); `install_mcp_ui_redaction()` wired into `bases/api/src/factory/api/main.create_app()` |
| bd-r6kki | #604 | lo1g9.3 | `WildcardRender` + `detectCarrier` predicate multiplex in `tool-renderers.tsx`; nested `{type:"resource"}` AND flat `{uri, mimeType}` shapes both detected; mcp-ui first, A2UI second, plain third |
| bd-eyahj | #606 | lo1g9.4 | Consumer: `<McpUiFrame>` + `<McpUiErrorBoundary>` + `mcp-ui-validator.ts` (Zod + tool/intent allowlists + mimeType normalizer) + `mcp-ui-origin-allowlist.tsx` + `lib/security/csp.ts` (CSP module + `next.config.ts` wiring) |
| bd-v2dko | #602 | lo1g9.5 | Producer: `ui_paint_uiresource(payload, mode, name?)` with three modes; companion byte-trace canary verifies FastMCP wrapping + `FactoryMCPClient` JSON-reparse path |

The producer `ui_paint_uiresource` lives at `components/ui/src/factory/ui/mcp/paint_uiresource.py:61-134`. It returns the spec-nested envelope `{type:"resource", resource:{uri:"ui://factory/<suffix>", mimeType, text|blob}}`. FastMCP wraps the dict as `TextContent` with the JSON-stringified body — the byte-trace canary asserts `FactoryMCPClient` extracts `uri+mimeType` via the JSON-reparse path (production scenario when an mcp-ui server is mounted upstream of the chat agent). The tool name is added to the chat allowlist `_EXTRA` in `components/agent/src/factory/agent/runtime/adapters/strands_mcp_chat_filter.py`.

### Decision rule across all five carriers

When the agent needs to render something:

1. **A2UI catalog covers it** → carrier #1 (`ui_paint_chat`) for free-form, or `ui_render_brick_view` for an existing brick view. Stays in chat scrollback.
2. **Canvas-tab paint** → carrier #2 (`ui_paint_canvas`) into one of `{graph, timeline, findings, live}`. Survives chat scroll; persists across the run.
3. **Watch-live for a sub-agent** → carrier #3 producer was removed with the legacy executors (#105); ACTIVITY events for swarm/graph spans are pending the strands.multiagent migration (#107).
4. **Typed React card already registered** → carrier #4 (`useComponent`-shaped tool call: `mini_graph_preview`, `finding_card`, `eval_result`).
5. **A2UI catalog can't express it** → carrier #5 (`ui_paint_uiresource`). Pick the safest mode that works: `remote_dom` (host-themed, no HTML injection) → `inline_html` (sandboxed iframe) → `external_url` (origin-allowlisted iframe).

### Sample payloads

```python
# remote_dom — safest. Host-themed component tree via mcp-ui RemoteDOM API.
ui_paint_uiresource(
    body="const c = document.createElement('ui-card'); c.setAttribute('title','Threat surface'); root.appendChild(c);",
    mode="remote_dom",
    name="Threat surface card",
)
# Wire mimeType: application/vnd.mcp-ui.remote-dom+javascript

# inline_html — arbitrary HTML/SVG/D3. Sandboxed iframe (allow-scripts only).
ui_paint_uiresource(
    body="<svg viewBox='0 0 100 100'><circle cx='50' cy='50' r='40' fill='red'/></svg>",
    mode="inline_html",
)
# Wire mimeType: text/html;profile=mcp-app — consumer normalizes to text/html
# at mcp-ui-validator.ts before forwarding to <UIResourceRenderer>

# external_url — embed a remote app. Requires user origin-allowlist confirm.
ui_paint_uiresource(
    body="https://dashboard.example.com/embed/run/abc123",
    mode="external_url",
)
# Wire mimeType: text/uri-list. <McpUiFrame> drops allow-same-origin from
# the SDK default sandbox; first-time confirm UX picks this-thread/always/never
```

### SDK gotchas (carrier #5)

- **MimeType normalization (validator + SDK strict-equality).** SDK strict-equality at `@mcp-ui/[email protected]/dist/index.mjs:21-22` rejects RFC 7231 params on `text/html` + `text/uri-list`, so a producer-emitted `text/html;profile=mcp-app` would fail mode dispatch. `mcp-ui-validator.ts` normalizes at the consumer (strips params for `text/html` and `text/uri-list`); `framework=react` on `application/vnd.mcp-ui.remote-dom+javascript` is **preserved** because RemoteDOM dispatch needs the framework hint.
- **Sandbox override (drops `allow-same-origin`).** SDK ships `sandbox="allow-scripts allow-same-origin"` for `external_url` at `@mcp-ui/[email protected]/dist/index.mjs:234`. `<McpUiFrame>` overrides to `allow-scripts` only — same-origin would let the iframe read host cookies and make same-origin XHRs back to `/ag-ui/run`. Pinned by a vitest snapshot in `mcp-ui-frame.test.tsx`.
- **postMessage validator (Zod + allowlist on top of SDK source-equality).** SDK's only check is source-window equality at `@mcp-ui/[email protected]/dist/index.mjs:175`. We layer a Zod discriminated union (tool|prompt|link|intent|notify) and two read-only allowlists on top: `ALLOWED_IFRAME_TOOLS` = `graph_get_app_topology`, `kb_search`, `memory_retrieve`; `ALLOWED_IFRAME_INTENTS` = `navigate-canvas`, `focus-finding`, `expand-card`. A `tool` action with any other name is rejected at the validator before reaching the host.
- **Two wire shapes accepted.** `detectCarrier` checks **both** `{type:"resource", resource:{uri:"ui://...", mimeType, ...}}` (spec-nested, what `ui_paint_uiresource` emits direct) AND `{text|image, uri:"ui://...", mimeType:"..."}` (post-flatten, what Strands' MCPClient produces after `FactoryMCPClient` preserves the fields). Producers always emit the nested form; the flat form arrives via upstream MCP server forwarding.
- **Logger redaction (T9, lo1g9.2).** `MCPUIRedactionFilter` walks log records and OTel spans, identifies UIResource shapes by the `ui://` URI scheme + danger MIME match, and replaces the body with `{uri, mimeType, size, sha256}`. Wired into `bases/api/src/factory/api/main.create_app()` via `install_mcp_ui_redaction()`. Without this, an `inline_html` payload with secrets in the script tag would land in plaintext logs/OTel spans.

### File map additions (lo1g9)

Producer + plumbing (Python):

- `components/ui/src/factory/ui/mcp/paint_uiresource.py` — bd-v2dko PR #602 producer (`ui_paint_uiresource(body, mode, name?, uri_suffix?)`).
- `bases/api/src/factory/api/main.py` — bd-0x2jq T9 `install_mcp_ui_redaction()` wiring.
- `components/agent/src/factory/agent/runtime/adapters/strands_mcp_chat_filter.py` — chat allowlist `_EXTRA` includes `ui_paint_uiresource`.

Consumer (TS/React):

- `frontends/next-dashboard/components/chat/mcp-ui-frame.tsx` — bd-eyahj PR #606 (191 LOC) `<McpUiFrame>` mounts `<UIResourceRenderer>`; sandbox override + chrome bar + Report + 600px max-height.
- `…/components/chat/mcp-ui-error-boundary.tsx` — sibling of `<InlineViewErrorBoundary>` (58 LOC).
- `…/components/chat/mcp-ui-validator.ts` — Zod discriminated union + tool/intent allowlists + mimeType normalizer (182 LOC).
- `…/components/chat/mcp-ui-origin-allowlist.tsx` — `external_url` confirm UX (167 LOC).
- `…/lib/security/csp.ts` — CSP module wired into `next.config.ts` (100 LOC).
- `…/lib/copilotkit/tool-renderers.tsx` — bd-r6kki PR #604 `WildcardRender` + `detectCarrier(parsed)` predicate multiplex (mcp-ui first, A2UI second, plain third).

## Smoke tests

```bash
# Backend integration: ToolResultEvent precedes StateDeltaEvent on the queue,
# round-tripped through map_chat_stream_event to AG-UI wire order.
# BE↔FE A2UI catalog parity canary fails fast on a new BE catalog
# entry that has no FE renderer (bd:python-factory-3hkqx round 3).
uv run pytest components/ui/test/factory/ui/test_canvas_paint_e2e.py \
              components/ui/test/factory/ui/test_a2ui_catalog_parity.py -v

# FE dispatcher: STATE_SNAPSHOT seeds, STATE_DELTA mutates, missing-parent
# patch is rejected without state mutation.
cd frontends/next-dashboard && \
  npx vitest run lib/copilotkit/__tests__/state-delta-canary.test.tsx

# FE A2UI flat → ReactAdapterNode tree transform — pins all three
# child-shape variants, orphan-ref drop, no double-render.
cd frontends/next-dashboard && \
  npx vitest run lib/copilotkit/__tests__/a2ui-tree.test.ts

# FE getRenderer lookup — case+underscore-insensitive parity with BE _norm.
cd frontends/next-dashboard && \
  npx vitest run components/renderer/__tests__/component-map.test.ts

# FE prop-alias canary — every catalog type's required_props value renders
# visibly in the DOM (bd-3hkqx round 4; mem a765bbd0 / 487b3ec5).
cd frontends/next-dashboard && \
  npx vitest run components/renderer/__tests__/renderers-prop-aliases.test.tsx

# FE decorative-prop pass-through canary — props.style + props.className
# survive ComponentRenderer's wrapper (bd-3hkqx round 6; mem 79f3b2b6 / e9deb353).
cd frontends/next-dashboard && \
  npx vitest run components/renderer/__tests__/renderers-style-passthrough.test.tsx

# E2E (requires API on :8000 + dashboard on :3000):
# scenario 2 paints a graph; scenario 3 paints the live tab.
cd frontends/next-dashboard && npx playwright test e2e/canvas-paint.spec.ts
```

## File map

```
components/ui/src/factory/ui/
├── mcp/
│   ├── paint_canvas.py                        # bd-D producer (carrier #2); bd-3hkqx slot rename canvas→live + COMPONENT_CATALOG type allowlist + props.children lift dispatch
│   ├── paint_canvas_lift.py                   # bd-3hkqx round 3: lift_props_children flat-sibling normalizer (carved out, <200 LOC)
│   ├── paint_chat.py                          # bd-zg93f Round 7: ui_paint_chat free-form A2UI inline in chat (carrier #1 producer; sibling of paint_canvas minus _a2ui_canvas sentinel)
│   └── render_brick_view.py                   # bd-C producer (carrier #1)
├── runtime/
│   ├── adapters/inline_html_adapter.py        # bd-kxpnf Round 7: renamed from mcpui_adapter.py / McpUiAdapter; frees @mcp-ui namespace for bd-lo1g9
│   ├── ag_ui_mapper_chat.py                   # _DISPATCH wires state_delta
│   ├── ag_ui_mapper_chat_state.py             # bd-D STATE_SNAPSHOT/DELTA emit
│   └── ag_ui_mapper_activity.py               # carrier #3 mapper

components/agent/src/factory/agent/
├── plugins/
│   ├── __init__.py                            # legacy plugin namespace (empty; #105)
│   ├── _bridge_common.py                      # AG-UI bridge helpers (bd:python-factory-ntyz7)
│   └── mcp_result.py                          # MCP result normalizers
├── runtime/
│   ├── adapters/strands_mcp_chat.py           # bd-D plugin registration order
│   ├── adapters/strands_mcp_client_factory.py # bd-nmzlk Round 7: FactoryMCPClient — preserves EmbeddedResource.uri/mimeType (sunset on upstream #2251/#2370 fix; `.agents/steering/upstream-sdk-shims.md` sunset table)
│   ├── companion/prompt.py                    # bd-I + bd-B prompt teaching
│   └── models.py                              # bd-D StateDeltaEvent variant

frontends/next-dashboard/
├── lib/copilotkit/
│   ├── tool-renderers.tsx                     # carrier #1 wildcard
│   ├── agent-components.tsx                   # bd-B carrier #4 registrations
│   ├── subagent-activity-renderer.tsx         # carrier #3 renderers
│   ├── provider.tsx                           # renderActivityMessages prop
│   ├── frontend-tools.tsx                     # bd-F adds "live" view label
│   ├── a2ui-canvas-slots.ts                   # bd-F slot helpers + memo; bd-3hkqx r3 delegates transform to a2ui-tree.ts
│   ├── a2ui-tree.ts                           # bd-3hkqx r3: a2uiToReactAdapterNodes (A2UI flat → tree, defensive 3-shape)
│   └── __tests__/
│       ├── state-delta-canary.test.tsx        # bd-H FE canary
│       ├── a2ui-tree.test.ts                  # bd-3hkqx r3: 3-shape transform pin
│       └── use-component-canary.test.tsx      # bd-B carrier #4 canary
├── lib/hooks/
│   └── use-copilot-state.ts                   # bd-E useAgent subscription
├── components/renderer/
│   ├── component-map.ts                       # bd-3hkqx r3: getRenderer (case+underscore-insensitive); 23 catalog types + Spacer/Divider
│   ├── component-renderer.tsx                 # bd-3hkqx r3: pivoted to getRenderer(key) ?? FallbackComponent
│   ├── renderers-layout.tsx                   # bd-3hkqx r3: SpacerRenderer + DividerRenderer
│   └── __tests__/component-map.test.ts        # bd-3hkqx r3: getRenderer lookup pins
├── components/renderer/__tests__/
│   ├── renderers-prop-aliases.test.tsx        # bd-3hkqx r4: catalog↔renderer prop-name parity (19 cases)
│   └── renderers-style-passthrough.test.tsx   # bd-3hkqx r6: decorative-prop pass-through (23 cases)
├── components/canvas/
│   ├── canvas.tsx                             # bd-F LiveView wiring
│   ├── live-view.tsx                          # bd-F generic "Live" tab; reads state.canvas.live (bd-3hkqx slot rename)
│   ├── graph-view.tsx                         # bd-F reads slot.graph
│   ├── timeline-view-v2.tsx                   # bd-F reads slot.timeline
│   └── findings-view.tsx                      # bd-F reads slot.findings
├── e2e/canvas-paint.spec.ts                   # bd-H playwright
└── vitest.config.ts                           # bd-H @ag-ui/client alias

components/ui/test/factory/ui/
├── test_canvas_paint_e2e.py                   # bd-H plugin ordering pin
└── test_a2ui_catalog_parity.py                # bd-3hkqx r3: BE↔FE catalog drift canary

.agents/
├── steering/a2ui-protocol.md                  # bd-A canonical four-carrier
├── recipes/useComponent-trigger-taxonomy.md   # bd-B carrier #4 taxonomy
├── recipes/canvas-aware-chat.md               # FE-tool round-trip
└── recipes/agent-driven-ui.md                 # this file (bd-J)
```

## Extension recipe — adding a new canvas slot

The slot enum is defined in three places that must move together:

1. `components/ui/src/factory/ui/mcp/paint_canvas.py` — add to `_VALID_TARGETS` and the `Literal` type on `ui_paint_canvas(target=...)`.
2. `components/agent/src/factory/agent/plugins/state_delta_plugin.py` — add to the `_VALID_TARGETS` frozenset (defensive validation in the hook).
3. `components/agent/src/factory/agent/runtime/models.py` — extend `StateDeltaEvent.target: Literal[...]`.

Then the FE side:

4. `frontends/next-dashboard/lib/copilotkit/a2ui-canvas-slots.ts` — add the slot to `CanvasState`.
5. `frontends/next-dashboard/lib/types/workbench.ts` — add to `CanvasViewId`.
6. `frontends/next-dashboard/lib/copilotkit/frontend-tools.tsx` — add to `VIEW_IDS` + `VIEW_LABELS` so `fe_navigate_canvas` accepts it.
7. `frontends/next-dashboard/components/canvas/canvas.tsx` — register a consumer view (model on `<LiveView />` if you don't need bespoke chrome).

Update tests in `test_paint_canvas.py` and `test_state_delta_plugin.py` so the validation matrices include the new target.

## Extension recipe — adding a new useComponent typed card

1. Create `frontends/next-dashboard/lib/copilotkit/agent-components/<name>.tsx` exporting a Zod schema and a render component.
2. Register in `lib/copilotkit/agent-components.tsx` via `useComponent({name, description, parameters, render})`. The description IS what the LLM sees — make it specific.
3. Add a section to `.agents/recipes/useComponent-trigger-taxonomy.md` (When-to / When-NOT-to / Example-trigger).
4. Update prompt teaching at `components/agent/src/factory/agent/runtime/companion/prompt.py` if the taxonomy changes the decision tree.
5. Pin the new card in `__tests__/use-component-canary.test.tsx` so future CopilotKit upgrades fail fast.

## Children of EPIC python-factory-iet5

| bd | Memory | Landed |
|---|---|---|
| bd-A `axuj` | `86e40334-51a1-4d53-9105-76b2a3c564b3` | `a2ui-protocol.md` rewrite around the four-carrier model |
| bd-B `deep` | `5ee9a3eb-b466-4a1a-aa7f-2dd105171385` | useComponent trigger taxonomy + prompt teaching + canary |
| bd-C `5om0` | `de074119-4b93-4398-ad59-d5779bc41f00` | `ui_render_brick_view` MCP tool (lights up 21 brick views) |
| bd-D `syh1` | `508f6e27-45f0-4616-930c-3b6a19d58466` | `ui_paint_canvas` + `StateDeltaEvent` + `state_delta_plugin` |
| bd-E `ewde` | `c12aae17-7266-4010-a68a-25e9ea833370` | Un-stubbed `useCopilotCanvasState` reads via `useAgent` |
| bd-F `olra` | `237c9336-e966-46b3-8f19-22b5e78339f0` | Canvas views consume `state.canvas.<slot>`; new "Live View" tab |
| bd-G `b4rc` | `a6fc807b-0080-435b-8d32-5b9682eb313f` | Deleted SessionBridge + 5 session tools + `_map_a2ui_output` (−891 LOC) |
| bd-H `pws3` | `9dc7566e-3de1-4f5b-a23c-cd6482a9fa4e` | QA canaries (vitest STATE_DELTA + pytest e2e + playwright) |
| bd-I `df96` | `c6d67f24-9eb6-4c74-98b3-1420e698ba12` | Chat allowlist `_EXTRA` + prompt teaching for brick views |
| bd-J `hjws` | (this doc) | End-to-end recipe |
| bd-3hkqx | `016965bd-cdc8-45cd-b2e3-99b7172e40d8` (design) · `a0d27dae-fb40-41d1-8a8c-cde63ae6e81a` (implement) · `484c110d-ef57-4280-8e8c-40647f292bbb` (debug+render-fix) · `aca2e1d6-3662-41dd-b54b-676475d032da` (UX-fix round 2: slot rename + type allowlist + FE handler guard) · `c2a3ecd0-4a88-4d68-a26b-b36c62da4d20` (round 3: BE↔FE A2UI boundary contract) · `a765bbd0-c241-4129-a4ce-8cac86f9d149` (round 4 implement) · `487b3ec5-f006-4946-9662-b203b2dc83c5` (round 4 qa-tester verdict) · `79f3b2b6-2342-4fb3-9249-ba4e4bba228b` (round 6 implement) · `e9deb353-5a9b-4a54-90f9-35b99e682210` (round 6 qa-tester verdict) | Single-prefix fix on chat allowlist (FLAT view path) + filter extraction to `strands_mcp_chat_filter.py`; suppresses raw `<brick>_get_views` so the agent prefers `ui_render_brick_view`. Consumer-side render fix: carrier #2 `_extract_a2ui_canvas` now handles `{text:"<json>"}` MCP content blocks (was wire-silent — no `STATE_*` reached the FE); carrier #1 `<InlineView>` hoisted outside the collapsible `<ToolCallCard>` so A2UI paints are visible by default (the chrome stays as trace metadata per the four-carrier doc intent). UX-fix round 2 (strands-expert design `56d2c5b6-8157-46ea-a128-64f6876a987e`): renamed the fourth slot `canvas → live` so the slot key matches the FE Live view id (state shape is now `{graph, timeline, findings, live}`); added a `COMPONENT_CATALOG` allowlist on `ui_paint_canvas` (case- and underscore-insensitive — unknown types return a structured error enumerating the catalog); `fe_navigate_canvas` handler now validates `view ∈ VIEW_IDS` because CopilotKit-core does not enforce the Zod schema at runtime, plus a `label || viewId` fallback in `openTab` to prevent blank tabs. **Round 3 (BE↔FE A2UI boundary contract, meta-architect verdict `cec79d55-7ff3-41c0-b583-781bc5d7d2b7`):** producer-side `props.children` lift carved out to `paint_canvas_lift.py::lift_props_children` so the canonical wire stays flat-siblings-with-`parent:`-refs (recursive, multi-level nesting collapses); FE flat→tree transform `a2uiToReactAdapterNodes` extracted to `a2ui-tree.ts` (un-stubs the previous `usePaintedComponents` cast — now a real transform handling all three child-shape variants, dropping orphan `parent:` refs, never double-rendering); FE `component-map.ts` exposes `getRenderer(name)` with case+underscore-insensitive lookup mirroring BE `paint_canvas.py:_norm`; `component-renderer.tsx:27-28` pivots from exact-key `COMPONENT_MAP[k]` to `getRenderer(k)`; new `SpacerRenderer` + `DividerRenderer` ship in `renderers-layout.tsx` so all 23 BE catalog types resolve (the four form-input types fall through to `CustomRenderer` pending dedicated renderers — discovered-from follow-up bd to file); `test_a2ui_catalog_parity.py` reads `component-map.ts` as text and asserts BE↔FE type-set parity by construction so future drift fails fast. **Round 4 (prop-alias contract, memory `a765bbd0`; qa-tester `487b3ec5`):** three-way prop-name drift fixed for `Text` and `Alert` — BE catalog (`Text.required_props=["text"]` with `content`/`value` aliased; `Alert.required_props=[]` with `message`/`description`/`title` in `optional_props`), FE renderers (`TypographyRenderer` reads `text ?? content ?? value`; `AlertRenderer` reads `description ?? message` for body, `title ?? message` for heading), and `renderers-prop-aliases.test.tsx` (19 cases) pin each catalog type's `required_props` value rendering visibly in the DOM. **Round 6 — decorative-prop pass-through wrapper in `ComponentRenderer`; agent's gradient/neon/colored decorations now reach the DOM.** `props.style` was dropped by every A2UI renderer; `props.className` was dropped by ~8 renderers (StatusDot/TrendBadge/Sparkline/FilterBar et al). `ComponentRenderer` now wraps rendered output in `<div style={...} className={...}>` when either decorative prop is present (Option A from qa-tester verdict). Pinned by `renderers-style-passthrough.test.tsx` (23 cases, was 14 RED / 9 GREEN before the fix; now 23/23 GREEN). Resolves bd:python-factory-0zdqf (P0). Resolves bd:python-factory-dv4bo (Text P0) and bd:python-factory-l6ypd (Alert P1) by the same change. |

## Children of EPIC python-factory-7z6rm (Round 7)

| bd | Memory | Landed |
|---|---|---|
| bd-zg93f | `293c185e` (strands-expert design) · `d0cdb475` (meta-architect HYBRID verdict) · `71749b2c` (implementer) | `ui_paint_chat` MCP tool — free-form A2UI inline in chat; carrier #1 producer #3. Mirror of `paint_canvas` minus `_a2ui_canvas` sentinel. Returns `{components, name}` so the existing wildcard `useDefaultRenderTool` paints it via `<InlineView>`. Zero FE changes. |
| bd-kxpnf | `5c3de106` (refactorer) | `McpUiAdapter → InlineHtmlRenderAdapter` rename. File `mcpui_adapter.py → inline_html_adapter.py`; `adapter_type "mcp-ui" → "inline-html"`; content_type `application/vnd.mcp-ui+json → application/vnd.factory.inline-html+json`. Frees the `@mcp-ui` namespace for real SDK adoption under bd-lo1g9. Zero behavior change. |
| bd-nmzlk | `bcebadb4` (strands-expert) | `FactoryMCPClient` Strands subclass. Preserves `EmbeddedResource.uri` + `mimeType` through the content-block flatten that Strands `MCPClient.map_mcp_content_to_tool_result_content` drops. Listed in `.agents/steering/upstream-sdk-shims.md#active-upstream-prs-were-watching` (sunset on upstream #2251/#2370 fix + pin bump). Hard prereq for carrier #5. |
| bd-lo1g9 | (filed, not started) | Real `@mcp-ui/client` adoption epic. Scope: install `@mcp-ui/client` in `frontends/next-dashboard`; wire carrier #5 mapper consuming `EmbeddedResource` blocks now preserved by `FactoryMCPClient`; render `ui://` URIs through `<UIResourceRenderer>` with iframe sandboxing. **`security-engineer` consult mandatory** before merge — first time external/agent-emitted content reaches a non-React DOM tree. |
