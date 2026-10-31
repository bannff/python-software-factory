# Recipe: Canvas-Aware Chat (FE Tool Round-Trip)

End-to-end walkthrough of the `fe_navigate_canvas` round-trip — the chat agent drives the the control-plane runtime workbench via a CopilotKit v2 `useFrontendTool` registration, while pushed canvas state via `useAgentContext` keeps it situationally aware. The goal here is to leverage **CopilotKit + Strands as designed, with no bespoke transport layer**. Three SDK gaps had to be filled (all cited below with their upstream issue); everything else is the SDKs doing their jobs. Closes the loop on top of bd-eyuj / bd-47sl / bd-tpfk (thinking trio) and bd-vw04 / bd-115z / bd-ioyz / bd-n368 / bd-3hkqx (canvas + FE-tool wire shape). Memory: implementer landing `96a217dc-3f3a-43aa-b74d-85c10142f273`; bd-3hkqx UX-fix round 2 `aca2e1d6-3662-41dd-b54b-676475d032da`.

> **Persona note (bd:python-factory-hadbi.1).** The chat agent is now an `AgentConfig` registration (`the control-plane runtime-default`, `defaults_companion_x.py`) resolved via the `COMPANION_X_CHAT_AGENT_ID` env var. Cache key + `Agent.name` + `FileSessionManager.session_id` all use `f"{agent_id}-{thread_id}"` so swapping the env yields a clean session boundary. The FE-tool round-trip described here is persona-agnostic — a future wine or workout chat agent inherits the same `fe_navigate_canvas` + `state_delta` plumbing without code changes. End-to-end walkthrough: `.agents/recipes/domain-agnostic-substrate.md`.

## Bricks Used
- `agent` — `ChatAgentPort.stream(fe_tools=..., messages=...)`, `FrontendToolPlugin`, `_StubAgentTool`, `FrontendToolSpec`, `maybe_apply_resume`
- `ui` — AG-UI mapper suppresses `TOOL_CALL_RESULT` for `_frontend_pending` payloads
- `api` (base) — `POST /ag-ui/run`, `parse_fe_tools`, `prefix_context`, threads full `messages[]` through

Plus the FE side: `frontends/next-dashboard/lib/{copilotkit,workbench-context}`.

## Prerequisites
- the control-plane runtime API running on `http://localhost:8001` and Next dashboard on `http://localhost:3000`.
- `COMPANION_X_CHAT_MODEL` set to any chat-capable model.
- No AWS, Docker, or Neo4j required.

## Lifecycle (one turn)

```
 1. FE registers fe_navigate_canvas (useFrontendTool) and publishes canvas state (useAgentContext)
 2. POST /ag-ui/run  →  body.tools[]  +  body.context[]  +  body.messages[]
 3. api base — parse_fe_tools → list[FrontendToolSpec]; prefix_context prepends labelled block;
    messages threaded to ChatAgentPort.stream
 4. ChatAgentPort.stream(thread_id, prefixed_msg, fe_tools=[…], messages=[…])
 5. maybe_apply_resume scans trailing role=tool entries from messages; if any patch a
    _frontend_pending sentinel on agent.messages, returns prompt=None (resume) — otherwise
    returns message unchanged (first turn)
 6. FrontendToolPlugin.attach(fe_tools) — BeforeInvocationEvent registers _StubAgentTool
    on Agent.tool_registry.dynamic_tools (legitimate Strands API; BeforeModelCallEvent.tool_specs
    is read-only — see SDK-First in dev-principles.md)
 7. LLM emits tool_use for fe_navigate_canvas
 8. _StubAgentTool.stream() yields ToolResultEvent({_frontend_pending: True, name, args})
    and sets request_state["stop_event_loop"] = True
 9. Strands ends the turn cleanly. AGUIBridgePlugin._on_after_tool publishes ToolResultEvent
    to the chat-stream queue.
10. ag_ui_mapper_chat._on_tool_result detects payload._frontend_pending and emits
    TOOL_CALL_END only (no TOOL_CALL_RESULT). Marks tcid as emitted so finalize-synth
    on `done` does not re-inject a synthetic RESULT.
11. AG-UI client's defaultApplyEvents finalizes the assistant message's toolCalls[] but
    does NOT push a {role:"tool", toolCallId, content} entry into messages[] (because
    no TOOL_CALL_RESULT was emitted).
12. CopilotKit's processAgentResult sees newMessages.findIndex(...) === -1 → invokes the
    useFrontendTool handler → workbench.switchView(view) runs.
13. CopilotKit re-POSTs /ag-ui/run with the new {role:"tool", toolCallId, content} reply
    appended to messages[].
14. Resume turn: maybe_apply_resume matches the new trailing role=tool to the sentinel on
    agent.messages, patches it with the FE handler's content, returns prompt=None. Strands
    resumes from the patched history without re-injecting the user prompt; the LLM sees
    the real reply, not the sentinel, and moves on.
15. AfterInvocationEvent strips the FE-stub registrations.
```

### SDK Gaps Bridged

Three upstream gaps the design fills — all cited so a future reader can check whether the SDKs have closed them:

- **Strands has no per-invocation tool-injection API.** `BeforeModelCallEvent.tool_specs` is read-only. Filled by `FrontendToolPlugin` → `ToolRegistry.register_dynamic_tool`, scoped to the per-thread `Agent` and torn down in `AfterInvocationEvent`.
- **CopilotKit v2 reads the absence of `TOOL_CALL_RESULT` to mean "FE tool needs dispatching",** but Strands' tool executor requires every `AgentTool.stream()` to yield a `ToolResultEvent` (see `tools/executors/_executor.py:244`). The deferred-sentinel pattern keeps the Strands executor happy; the AG-UI mapper-side suppression keeps the CopilotKit dispatcher happy. One pattern bridges both SDKs without violating either contract. Verdicts: strands-expert `0d78bcac-f180-40b2-8eee-e9ffa4396645`, meta-architect `a807368d-28db-4598-8e50-59a4e993bda2`.
- **CopilotKit-core does NOT enforce `useFrontendTool` Zod schemas at runtime.** The Zod parameters are converted to JSON Schema once via `zodToJsonSchema` for tool advertisement (`@copilotkitnext/[email protected]/dist/index.mjs::createToolSchema`); `executeSpecificTool` (same bundle, lines 886-940) only does `JSON.parse` on `toolCall.function.arguments` and hands the result to `tool.handler` directly — no `tool.parameters.parse` / `safeParse`. The FE handler is therefore the first and only validator of its own input; FE handlers MUST validate inputs explicitly. `fe_navigate_canvas` guards with `if (!VIEW_IDS.includes(view)) return {success:false, error:"unknown view ..."}` and `openTab` falls back to `label || viewId` so a malformed call can never produce a blank tab. Debugger evidence: `.scratch/bd-3hkqx-ux-bugs/VERDICT.md` (Bug C); strands-expert design `56d2c5b6-8157-46ea-a128-64f6876a987e`, implementer landing `aca2e1d6-3662-41dd-b54b-676475d032da`.

## Code Snippets

### FE — register the tool

```tsx
// frontends/next-dashboard/lib/copilotkit/frontend-tools.tsx
import { z } from "zod";
import { useFrontendTool } from "@copilotkit/react-core/v2";
import { useWorkbenchContext } from "@/lib/workbench-context";

export function FrontendTools() {
  const workbench = useWorkbenchContext();
  useFrontendTool({
    name: "fe_navigate_canvas",                 // fe_ prefix is mandatory
    description: "Switch the the control-plane runtime canvas to a different view.",
    parameters: z.object({ view: z.enum(["welcome", "graph", "findings", /* … */]) }),
    handler: async ({ view }) => {
      workbench.switchView(view);
      return { success: true, view };
    },
  });
  return null;
}
```

Mounted inside `<CopilotKitProvider>` and `<WorkbenchProvider>` — see `provider.tsx`. `WorkbenchProvider` lives above `CopilotKitProvider` in `app/layout.tsx`.

### Wire shape — END only for FE tools

```
TOOL_CALL_START toolCallId=tc-... toolCallName=fe_navigate_canvas
TOOL_CALL_ARGS  toolCallId=tc-... delta='{"view":"graph"}'
TOOL_CALL_END   toolCallId=tc-...
RUN_FINISHED
```

That's it. **No `TOOL_CALL_RESULT` for FE tools.** CopilotKit's dispatcher fires when it sees an assistant `toolCalls[]` with no matching `{role:"tool"}` reply (the `findIndex(m => m.role === "tool" && m.toolCallId === id) === -1` predicate in `@copilotkitnext/core` `processAgentResult`). Server-side tools are unaffected — they still emit the canonical `TOOL_CALL_END` + `TOOL_CALL_RESULT` pair.

## File Map

| Hop | File | Role |
|-----|------|------|
| FE — workbench state | `frontends/next-dashboard/lib/workbench-context.tsx` | `WorkbenchProvider` lifts state above `CopilotKitProvider` |
| FE — push context | `frontends/next-dashboard/lib/copilotkit/canvas-context.tsx` | `<CanvasContextBridge />` calls `useAgentContext` (bd-vw04) |
| FE — register tool | `frontends/next-dashboard/lib/copilotkit/frontend-tools.tsx` | `<FrontendTools />` calls `useFrontendTool` (bd-115z) |
| FE — agent identity | `frontends/next-dashboard/lib/copilotkit/companion-agent.ts` | Exports `COMPANION_X_AGENT_ID` + `createCompanionXAgent()` factory; single source of truth shared by FE provider and BE runtime route (bd:python-factory-sopw) |
| FE — wiring | `frontends/next-dashboard/lib/copilotkit/provider.tsx` | Mounts both bridges inside the CopilotKit provider. Registers `the control-plane project` via `selfManagedAgents` (NOT `runtimeUrl`) so `core.agents` is populated synchronously and inspector + chat share one `HttpAgent` instance (bd:python-factory-sopw) |
| FE — inspector workaround | `frontends/next-dashboard/lib/copilotkit/inspector-attach-workaround.tsx` | Idempotent post-mount toggle of `<cpk-web-inspector>.core` to fire `attachToCore` — bridges upstream `@copilotkitnext/[email protected]` gap where the inspector's `set core(value)` setter doesn't wire subscriptions on initial React-driven assignment (bd:python-factory-sopw). Removable when upstream patches. |
| FE — runtime route | `frontends/next-dashboard/app/api/copilotkit/[[...path]]/route.ts` | Hono catch-all that proxies CopilotKit v2 traffic to the Python `/ag-ui/run` endpoint. Imports `COMPANION_X_AGENT_ID` from `companion-agent.ts` so FE/BE registration never drifts (bd:python-factory-sopw). |
| API — endpoint | `bases/api/runtime/ag_ui_routes.py` | `POST /ag-ui/run` calls `parse_fe_tools` + `prefix_context`, threads `fe_tools` and full `messages[]` through |
| API — parsing | `bases/api/runtime/ag_ui_input.py` | `parse_fe_tools` validates against `FrontendToolSpec`; `prefix_context` prepends labelled block |
| Agent — contract | `components/agent/runtime/models.py` | `FrontendToolSpec` Pydantic model |
| Agent — port | `components/agent/runtime/chat_port.py` | `ChatAgentPort.stream(thread_id, message, fe_tools=..., messages=...)` |
| Agent — adapter | `components/agent/runtime/adapters/strands_mcp_chat.py` | Wires `FrontendToolPlugin` per-thread; calls `maybe_apply_resume` to patch sentinels on resume turns |
| Agent — resume helper | `components/agent/runtime/adapters/strands_mcp_chat_resume.py` | Selective Option A — patches `_frontend_pending` sentinels on `agent.messages` from trailing `role:"tool"` entries in `RunAgentInput.messages` |
| Agent — plugin | `components/agent/plugins/frontend_tool_plugin.py` | Registers stubs in `BeforeInvocationEvent`, strips in `AfterInvocationEvent` |
| Agent — plugin | `components/agent/plugins/parallel_tool_dedup.py` | `ParallelToolDedupPlugin` — per-turn dedup of duplicate `(name, JSON-canonical input)` `tool_use` blocks via `BeforeToolCallEvent.cancel_tool`. Always-on alongside `FrontendToolPlugin` / `AGUIBridgePlugin` / `LearningRecallPlugin` (bd:python-factory-ads4). |
| Agent — stub | `components/agent/plugins/_frontend_stub_tool.py` | Deferred sentinel + `stop_event_loop=True`; enforces `fe_` prefix |
| UI — surface | `components/ui/runtime/ag_ui_mapper_chat.py` | `_on_tool_result` filters `_frontend_pending` and emits **TOOL_CALL_END only** (no RESULT). Marks tcid in `result_emitted_tcids` so finalize-synth does not re-inject. |

## Adding a New FE Tool

The handler interprets `parameters` opaquely — no Python work required.

```tsx
useFrontendTool({
  name: "fe_focus_tab",
  description: "Focus a canvas tab by id.",
  parameters: z.object({ tabId: z.string() }),
  handler: async ({ tabId }) => { workbench.focusTab(tabId); return { success: true, tabId }; },
});
```

The api base validates the new entry as a `FrontendToolSpec` (any object schema), `_StubAgentTool._wrap_parameters` ensures `inputSchema.json` has `type: object`, and the LLM sees `fe_focus_tab` in its tool list for that turn.

## Manual Smoke Test

1. Start the API:
   ```bash
   set -a; source projects/the control-plane project/.env; set +a
   PYTHONPATH="$(find "$PWD/bases" "$PWD/components" -type d -path '*/src' | paste -sd: -)" \
     uv run python -m factory.api.main
   ```
2. Start the dashboard: `cd frontends/next-dashboard && npm run dev`.
3. Open `http://localhost:3000`, focus the chat sidebar, send `open the graph view`.
4. Verify in the network panel:
   - First `/ag-ui/run` POST has `tools[0].name = "fe_navigate_canvas"` and `context[0].value.activeView` matches the current view.
   - SSE stream contains `TOOL_CALL_START` + `TOOL_CALL_ARGS` + `TOOL_CALL_END` for the FE tool. There is **NO `TOOL_CALL_RESULT`** for the FE tool — that absence is the contract.
   - A second `/ag-ui/run` POST follows with `messages[-1].role = "tool"` and `messages[-1].toolCallId` matching the END.
5. Verify in the UI: canvas switched to Graph view, tool-call pill flipped to Complete (no infinite spinner — that was bd-3uhr).
6. Verify resume turn: send `now show me findings`. Canvas flips to Findings; the LLM does **not** re-emit `fe_navigate_canvas` for graph (proves `agent.messages` was patched with the prior FE handler reply via `maybe_apply_resume`).

## Success Criteria
- [ ] `tools[]` round-trips to `FrontendToolSpec` and back to a stub registration on the per-thread Strands `Agent`.
- [ ] `context[]` lands as a `Canvas context (system-supplied, FE-pushed):` block prepended to the user message.
- [ ] `_StubAgentTool` yields one `ToolResultEvent` with `_frontend_pending: True` and sets `stop_event_loop=True`.
- [ ] AG-UI mapper emits `TOOL_CALL_END` **only** for `_frontend_pending` payloads. No `TOOL_CALL_RESULT`. No finalize-synth.
- [ ] CopilotKit dispatcher sees the unresolved tool call (`newMessages.findIndex(m => m.role === 'tool' && m.toolCallId === ...) === -1`) and invokes the FE handler.
- [ ] CopilotKit re-POSTs with the `role=tool` reply; `maybe_apply_resume` patches the sentinel on `agent.messages` and returns `None` so Strands resumes without re-injecting the user prompt.
- [ ] After the turn, `ToolRegistry.dynamic_tools` no longer contains `fe_navigate_canvas`.

## API Reference

| Brick / Base | Import | Key Symbol |
|--------------|--------|------------|
| agent | `factory.agent.interface` | `FrontendToolSpec`, `get_chat_agent_stream` |
| agent | `factory.agent.runtime.chat_port` | `ChatAgentPort.stream(thread_id, message, fe_tools=..., messages=...)` |
| agent | `factory.agent.runtime.adapters.strands_mcp_chat_resume` | `maybe_apply_resume` |
| agent | `factory.agent.plugins.frontend_tool_plugin` | `FrontendToolPlugin(agent).{attach,detach,register_hooks}` |
| agent | `factory.agent.plugins._frontend_stub_tool` | `_StubAgentTool`, `FE_TOOL_PREFIX` |
| api | `factory.api.runtime.ag_ui_input` | `parse_fe_tools`, `prefix_context` |
| api | `factory.api.runtime.ag_ui_routes` | `register_ag_ui_routes` |

## MCP Tools

This round-trip is FE-side and chat-port-side; it does not add any tools to the brick aggregator. The chat agent continues to see the curated semantic subset (`companion/tools.py`) plus the FE stubs registered for the turn. FE stubs are scoped to the per-thread `Agent.tool_registry.dynamic_tools` and never appear in `list_bricks` / `get_brick_tools`.
