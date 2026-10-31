# Recipe: Timeline Page — UI Data Flow

End-to-end data flow from agent session events through the `timeline-view.tsx` renderer to the the control-plane runtime dashboard.

## Bricks Used
- `agent` — Via CopilotKit AG-UI state (steps and tool calls, live)
- `graph` — Persisted `ToolInvocation` history via `graph_list_recent_tool_invocations` (typed read, post-bd python-factory-c39g)

## Scenario

An agent session produces steps and tool calls via AG-UI Server-Sent Events. The timeline view renders these as a chronological feed with type-based filtering. Persisted history from prior runs is loaded on mount via the graph brick's typed reader so the tab is useful even before any new session starts.

## Prerequisites

- the control-plane runtime gateway running with CopilotKit AG-UI bridge
- Graph brick reachable through the MCP aggregator (any backend — `networkx` for local dev, `neo4j` for the full stack)
- Active agent session for live updates (history view works without one)

## Data Sources: AG-UI State Bridge + Graph Typed Read

Timeline data has two sources:

1. **Live (AG-UI):** CopilotKit's AG-UI integration pushes `steps` and `toolCalls` props via SSE events (`STEP_STARTED`, `STEP_FINISHED`, `TOOL_CALL_START`, `TOOL_CALL_END` + `TOOL_CALL_RESULT`). Tool completion is the END+RESULT pair (AG-UI v0.0.47); see [`a2ui-protocol.md`](../steering/a2ui-protocol.md#tool-call-lifecycle-the-end--result-pair-ag-ui-v0047).
2. **Persisted (graph brick):** `useTimelineData` (in `lib/hooks/use-timeline-data.ts`) calls `graph_list_recent_tool_invocations(limit=100)` on mount. The typed tool returns flat `ToolInvocation` rows joined one-hop with their parent `Session` and sorted by `created_at` DESC. Rows are mapped through `lib/timeline-history.ts` to `TimelineEntry` objects. **No Cypher escape hatch is used** — the prior `TIMELINE_HISTORY_QUERY` Cypher path was retired in bd python-factory-c39g.

**Note:** `useCopilotCanvasState` is currently a stub returning empty arrays. Live timeline data flows through the `steps` and `toolCalls` props passed directly to the view component; persisted history flows through `useTimelineData`.

## Steps

### Step 1: Persisted History via Typed Tool

```typescript
// lib/hooks/use-timeline-data.ts — fetched on mount
const response = await callTool("graph_list_recent_tool_invocations", {
  limit: 100,
});
// Returns { result: { rows: [...], count: N, limit: 100 } }
// Each row is a flat dict: { tool_name, brick, success, latency_ms,
//   created_at, error, workflow_run_id, args_summary, caller,
//   result_summary, session_id, session_agent_id, session_principal_id }

// mapTimelineHistoryRows (lib/timeline-history.ts) flattens rows to TimelineEntry[]
// — typed tool wired in under bd python-factory-c39g; the prior
// TIMELINE_HISTORY_QUERY Cypher escape hatch is gone.
```

### Step 2: AG-UI Events → Props (Live)

```typescript
// timeline-view.tsx receives props from the canvas layout:
interface TimelineViewProps {
  steps: Step[];           // From AG-UI STEP_STARTED/STEP_FINISHED events
  toolCalls: ActiveToolCall[];  // From AG-UI TOOL_CALL_START + TOOL_CALL_END/TOOL_CALL_RESULT pair
  agentState: Record<string, unknown>;  // From AG-UI STATE_SNAPSHOT/STATE_DELTA
}
```

### Step 3: Entry Construction

```typescript
// useMemo builds TimelineEntry[] from steps + toolCalls:

// Steps → timeline entries
for (const step of steps) {
  items.push({
    id: `step-${step.name}`,
    type: "step",
    title: step.name,
    status: step.status,  // "running" | "completed"
    timestamp: step.startedAt ?? Date.now(),
    duration: step.finishedAt && step.startedAt
      ? step.finishedAt - step.startedAt : undefined,
  });
}

// Tool calls → timeline entries (with security detection)
for (const tc of toolCalls) {
  const isFinding = tc.name?.startsWith("security_") || tc.name?.includes("posture");
  items.push({
    id: `tc-${tc.id}`,
    type: isFinding ? "finding" : "tool_call",  // Security tools tagged as "finding"
    title: tc.name || "Unknown tool",
    status: tc.active ? "running" : "completed",
    timestamp: Date.now(),
    detail: tc.args || undefined,
    severity: isFinding ? "medium" : undefined,
  });
}

// Sorted chronologically
items.sort((a, b) => a.timestamp - b.timestamp);
```

### Step 4: Filter Bar

```typescript
// Four filter types: all | step | tool_call | finding
const FILTERS = [
  { id: "all", label: "All" },
  { id: "step", label: "Steps" },
  { id: "tool_call", label: "Tool Calls" },
  { id: "finding", label: "Findings" },
];

// Active filter styled with violet pill (bg-violet-500/10 text-violet-400)
// Entry count shown: "{filtered.length} entries"
```

### Step 5: Frontend Rendering

```typescript
// timeline-view.tsx — custom renderer, NOT BrickViewRenderer

// 1. Filter bar: pill buttons with active state highlight
// 2. Timeline entries: rendered via TimelineEntryCard component
//    - Each entry shows type icon, title, status, timestamp, duration
//    - Security tool calls get "finding" type with severity badge
// 3. Empty state: Clock icon + "Timeline populates as the agent works..."
// 4. Entries render in a space-y-0 layout (no gaps between cards)
```

### Step 6: Triggering Timeline Data (Agent Session)

```python
# During a live agent session, the AG-UI SSE stream emits:

# Step events:
# → STEP_STARTED: { name: "analyze_security", status: "running" }
# → STEP_FINISHED: { name: "analyze_security", status: "completed" }

# Tool call events (AG-UI v0.0.47 — completion is a PAIR):
# → TOOL_CALL_START:  { toolCallId: "tc-1", toolCallName: "security_run_analysis" }
# → TOOL_CALL_ARGS:   { toolCallId: "tc-1", delta: "{...}" }
# → TOOL_CALL_END:    { toolCallId: "tc-1" }                  ← bare close, no result field
# → TOOL_CALL_RESULT: { toolCallId: "tc-1", messageId: "<uuid4>",
#                       content: "<json>", role: "tool" }     ← creates role:"tool" message
# CopilotKit's reducer uses the RESULT message to flip the pill InProgress → Complete.

# These flow through CopilotKit's useCopilotChat → props → TimelineView
```

## Known Limitations

- Live updates only populate during an active agent session (CopilotKit state bridge)
- Persisted history is bounded by the `limit` arg (default 100) — no cursor pagination yet (tracked under bd python-factory-ovjz)
- `useCopilotCanvasState` is a stub — live data flows via direct props, not canvas state
- Tool call timestamps for *live* entries use `Date.now()` at render time, not the actual execution time. Persisted entries use the row's `created_at`.
- Security tool detection is pattern-based (`security_*`, `posture`) — may miss custom security tools

## Success Criteria

- [ ] Steps render as timeline entries with name, status, duration
- [ ] Tool calls render with tool name and completion status
- [ ] Security tools (`security_*`, `*posture*`) tagged as "finding" type
- [ ] Filter pills toggle between all/step/tool_call/finding
- [ ] Entry count updates when filter changes
- [ ] Chronological sort (earliest first)
- [ ] Empty state renders when no agent session is active

## API Reference

| Source | Event Type | Data Shape |
|--------|-----------|------------|
| AG-UI SSE | `STEP_STARTED` | `{name, status: "running", startedAt}` |
| AG-UI SSE | `STEP_FINISHED` | `{name, status: "completed", finishedAt}` |
| AG-UI SSE | `TOOL_CALL_START` | `{toolCallId, toolCallName}` (active=true client-side) |
| AG-UI SSE | `TOOL_CALL_ARGS` | `{toolCallId, delta}` (incremental args) |
| AG-UI SSE | `TOOL_CALL_END` | `{toolCallId}` — bare close, no result field |
| AG-UI SSE | `TOOL_CALL_RESULT` | `{toolCallId, messageId, content, role:"tool"}` — pairs with END, creates the `role:"tool"` message that flips the pill to Complete |
| React prop | `steps: Step[]` | Array of step objects from CopilotKit |
| React prop | `toolCalls: ActiveToolCall[]` | Array of tool call objects from CopilotKit |
| React hook | `useTimelineData()` | `{entries, loading, error, available, refresh}` — calls `graph_list_recent_tool_invocations` and maps rows via `mapTimelineHistoryRows` |

## MCP Tools

| Tool | Brick | Description |
|------|-------|-------------|
| `graph_list_recent_tool_invocations` | graph | `@deterministic`. Args: `limit=100, backend=""`. Returns the most recent `ToolInvocation` rows globally (no run scoping), one-hop joined with parent `Session`, sorted `created_at` DESC, with poll-noise filtered out. Drives the Timeline tab. For run-scoped reads use `graph_get_tool_invocations_for_run`. |
