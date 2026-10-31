# the control-plane runtime Runtime Observability Handoff

**Status:** In progress, ready for PR
**Area:** the control-plane runtime local runtime, Timeline, Metrics, tool visibility
**Date:** 2026-05-04

## What We Were Doing

The work shifted from general the control-plane runtime local setup into a focused observability pass for the lightweight local stack.

The concrete goals were:

- make local the control-plane runtime coherent with its actual lightweight runtime behavior
- wire the local chat path to Ollama so the dashboard could be tested without Bedrock
- verify whether tool calls were actually happening instead of trusting model text
- make Timeline honest about what is live-only versus historically persisted
- replace the old Metrics view, which was showing seeded generic metrics, with something grounded in real runtime telemetry

## What Changed

### Local runtime alignment

- `projects/the control-plane project/.env.example` now reflects a lightweight local stack: `networkx`, `sqlite`, `chromadb`, `amem`, memory-backed worker/storage defaults, and `ollama` as the local LLM backend.
- `projects/the control-plane project/README.md` was updated to document that local mode is live-first and lightweight, and to describe the Ollama startup path.
- `components/llm_gateway` gained first-class Ollama support, including provider and embedding adapter wiring.

### Chat and tool path cleanup

- the control-plane runtime chat stayed on the stable Strands chat path (now `StrandsMCPChatAgent` via the chat factory; legacy `StrandsChatAgent` was retired in bd:python-factory-5y8r).
- chat tool construction now prefers native per-tool Strands/MCP tools before falling back to the generic wrapper path
- explicit tool names mentioned in prompts are preserved during tool selection so directly requested tools are not filtered out
- AG-UI now passes `thread_id` into the tool context so downstream instrumentation can associate work with the current run

### Timeline semantics and lifecycle

- API health now exposes Timeline capabilities so the frontend knows whether historical Timeline is actually available
- the UI session bridge emits a matching `agent.session.end` lifecycle event with event counts
- Timeline copy was softened so lightweight mode does not imply durable session history when only live SSE is available

### Runtime metrics redesign

- the old brick-rendered Metrics page was removed from the main dashboard route
- Metrics is now a custom runtime telemetry view backed by the shared live Timeline buffer
- the live Timeline buffer was moved out of hook-local state so it survives tab switches and view remounts
- Metrics now shows runtime-oriented summaries such as buffered events, success rate, average latency, active entries, bricks touched, top tools, top bricks, and recent failures
- drill-down was added so clicking cards, top tools, top bricks, or failures opens the backing event list
- drill-down now supports compact status filters: `all`, `completed`, `failed`, `running`
- a lightweight focus handoff lets Metrics send a filtered slice into Timeline, where Timeline shows a focused live view with clearable context

## Direction We Were Taking

The direction is to treat the control-plane runtime observability as runtime-first and truthful to the current deployment mode.

That means:

- in lightweight local mode, prefer live telemetry and avoid pretending historical graph-backed observability exists when it does not
- keep the dashboard grounded in actual runtime events rather than seeded or domain-generic placeholders
- use small shared client stores only where needed instead of adding a heavy global state layer
- keep Timeline and Metrics tightly connected so Metrics summarizes and Timeline explains
- preserve the stable local chat path and expose tools more explicitly rather than chasing a more experimental integration path prematurely

## Verified Outcomes

- targeted Python tests passed earlier for chat tool construction and companion tool selection
- `npm exec tsc --noEmit` passed for the dashboard after the runtime metrics and Timeline refactor
- browser validation confirmed:
  - live Timeline entries survive tab switches
  - runtime Metrics is driven by the live buffer
  - drill-down panels open correctly
  - drill-down filters work
  - Metrics can hand a filtered slice into Timeline and Timeline renders that focused live view correctly

## What Is Next

The next useful slice is to deepen observability without regressing the lightweight local story.

### Highest-value next steps

1. Add second-dimension filtering inside runtime metrics drill-downs, especially by tool, brick, and status together.
2. Add a deliberate buffer management control so the user can reset or snapshot the retained live telemetry.
3. When persistent graph history is enabled, blend live and persisted history cleanly instead of treating them as unrelated views.
4. Decide whether external MCP invocations should also appear in the dashboard Timeline, and if so, instrument that path explicitly rather than assuming it already flows through the UI stream.
5. Add a small set of focused frontend tests around the shared live buffer and Timeline focus handoff so the tab-switch fix does not regress.

### Constraints to keep

- do not bring back seeded generic metrics as the primary Metrics experience
- do not imply durable session history unless the backend confirms graph-backed history is available
- avoid a heavyweight frontend state system unless multiple more complex cross-view interactions justify it

## PR Framing

This change set is best described as a the control-plane runtime local runtime observability pass:

- align lightweight local mode and Ollama defaults
- improve real tool exposure in chat
- make Timeline honest and stable in lightweight mode
- replace generic Metrics with live runtime telemetry and drill-down
