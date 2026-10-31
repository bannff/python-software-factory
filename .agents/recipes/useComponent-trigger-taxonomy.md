# useComponent Trigger Taxonomy

CopilotKit v2's `useComponent` registers typed React components the LLM can
summon mid-stream by emitting a tool call with the registered name. It is
sugar over `useFrontendTool`: the hook builds a model-facing description,
forwards optional Zod parameters, and wraps the user's render in a
`render: ({ args }) => <Component {...args} />` closure
(`frontends/next-dashboard/node_modules/@copilotkitnext/react/dist/hooks/use-component.mjs:55-66`).
The component renders inline in the chat bubble with the parsed args as props.

This is **Carrier #4** in `.agents/steering/a2ui-protocol.md` — typed inline
cards riding the existing tool spine. There is no new AG-UI event type;
`processAgentResult`
(`frontends/next-dashboard/node_modules/@copilotkitnext/core/dist/index.mjs:780-1290`)
routes the tool call to the FE handler that CopilotKit synthesised from
`useComponent`.

Three components ship today (Phase 1, bd-kzsl, register-only). This doc tells
the agent when to summon each — and just as importantly, when not to. Each
component file already carries a `description:` field that CopilotKit
auto-injects into the tool catalog the LLM sees; this taxonomy complements
that with usage rules the description alone can't carry.

## mini_graph_preview

**Args** (Zod, `agent-components/mini-graph-preview.tsx`):
`{ entity_id: string, depth?: number }`. v1 ships hop-1 only; `depth` is a
hint, not honored.

**When to summon**
- User wants a quick visual sanity-check on a single entity:
  "show me what's connected to X", "give me a graph of X",
  "what does X touch?".
- Grounding a single-entity question in a hop-1 neighborhood snapshot
  before answering in prose.

**When NOT to summon**
- User asks for a full topology / multi-hop map. Use the Graph canvas tab
  instead — call `fe_navigate_canvas("graph")`.
- The entity has more than ~50 connections. The card renders too dense to
  read; summarise in prose.
- Cross-entity comparisons. Two cards are noisy; prose with anchored ids
  is better.

**Example trigger**: `what does the kiro-agent user touch?` ·
`show me sandbox-bg-007's neighborhood` ·
`quick graph preview of arn:aws:iam::123:role/foo`.

## finding_card

**Args** (Zod, `agent-components/finding-card.tsx`):
`{ finding_id: string, cwe?: string, severity?: string }`.

**When to summon**
- User asks about a specific finding by id.
- Follow-up about a finding when the details are already loaded into the
  current thread from a security scan.

**When NOT to summon**
- Listing multiple findings. Use prose with bullet points, or
  `ui_render_brick_view("security")` for the full dashboard.
- Generic security questions ("what is SSRF?"). Explain in prose.
- Findings without a stable id. The card looks empty.

**Example trigger**: `what's the severity of finding F-2026-04-19?` ·
`tell me about that SSRF finding` ·
`pull up F-001`.

## eval_result

**Args** (Zod, `agent-components/eval-result.tsx`): `{ run_id: string }`.

**When to summon**
- User asks about a specific eval run by id.
- Surfacing one run's metrics (pass rate, P / R / F1) inline.

**When NOT to summon**
- Eval suite overviews. `ui_render_brick_view("evals")` is better.
- Cross-run comparisons. Multiple cards are noisy; render a chart or a
  prose summary.
- The run is still in progress. Summon only after `pass_rate` is final.

**Example trigger**: `summarise eval run rt-sast-2026-05-01` ·
`how did run de7aa4dc do?`.

## Decision tree

```
User asks →
  Specific entity / finding / run by id?            → typed `useComponent` card
  Generic dashboard / panel / brick view?           → `ui_render_brick_view`
  Switch the workbench canvas tab?                  → `fe_navigate_canvas`
  Paint a custom canvas state slot (carrier #2)?    → `ui_paint_canvas`
  One-line answer / quick clarification?            → prose
```

When in doubt, prefer prose. Brick views (`ui_render_brick_view`) cover
dashboards. Typed cards cover single-entity drill-downs. Brick views and
typed cards are not mutually exclusive — paint a brick view to surface a
panel and follow with a typed card to drill into the row the user named.

## How activation works (SDK pin)

The LLM emits a normal tool call with the registered name (e.g.
`mini_graph_preview`). CopilotKit's `processAgentResult` routes the call
to the FE handler synthesised by `useFrontendTool` under the hood, which
in turn renders `<Component {...parsedArgs} />` (`use-component.mjs:55-66`).
There is **no new AG-UI event type** — `useComponent` rides the existing
tool spine. The pill in the chat surface flips to `Done` on the canonical
`TOOL_CALL_END + TOOL_CALL_RESULT` pair, same as every other tool call.

This is what makes it Carrier #4 and not an off-band channel: the
producer (LLM) and the consumer (CopilotKit's tool dispatcher) speak the
same wire format the rest of the chat surface already uses.

## Canary

`frontends/next-dashboard/lib/copilotkit/__tests__/use-component-canary.test.tsx`
pins the dispatcher contract: registering a `useComponent`, firing a
synthetic AG-UI tool-call event, asserting the typed renderer mounts with
the parsed args. If a future CopilotKit upgrade refactors the
`useFrontendTool` wrapping or moves the dispatcher off `processAgentResult`,
this test fails fast.
