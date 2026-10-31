# Recipe: Findings Page — UI Data Flow (Gold Standard)

End-to-end data flow from security brick tool calls through the `findings-view.tsx` renderer to the the control-plane runtime dashboard. This page is the visual standard for the dashboard.

## Bricks Used
- `security` — Via tool call results from agent sessions (not direct MCP queries)

## Scenario

An agent runs a security scan during a live session. Tool call results flow through the CopilotKit state bridge into the `useFindings` hook, which extracts and normalizes findings for display.

## Prerequisites

- the control-plane runtime gateway running with CopilotKit AG-UI bridge
- Active agent session (findings only populate during live sessions)
- Security brick available in MCP aggregator

## What Makes This the Gold Standard

The findings page sets the visual bar for all dashboard views:

1. **Severity-colored filter pills** — `critical|high|medium|low|info` with count badges, toggle-to-filter
2. **AnimatePresence expand/collapse** — Smooth detail reveal via framer-motion
3. **Dual data source** — Merges persisted analyses (MCP) with live tool call results (AG-UI)
4. **Severity-sorted display** — Critical first, info last, always
5. **Consistent density** — Compact rows with severity pill, title, resource, chevron

## Steps

### Step 1: Data Sources (Two Paths)

```typescript
// Path A: Persisted analyses — fetched on mount
// useFindings calls security_security.list_analyses on mount
callTool("security_security.list_analyses", {})
// → { analyses: [{ analysis_id, target, findings: [{severity, title, resource, ...}] }] }

// Path B: Live tool calls — extracted from AG-UI state
// toolCalls prop comes from CopilotKit's useCopilotChat
// useFindings filters for security-related tool names:
const SECURITY_PATTERNS = [/^security_/, /posture/i, /threat/i, /vulnerability/i, /scan/i];
```

### Step 2: Finding Extraction from Tool Calls

```typescript
// useFindings hook processes completed tool calls:
for (const tc of toolCalls) {
  if (tc.active || !tc.result || !tc.name) continue;
  if (!isSecurityTool(tc.name)) continue;

  const result = JSON.parse(tc.result);
  // Extracts from result.findings, result.issues, or raw array
  const items = result?.findings ?? result?.issues ?? (Array.isArray(result) ? result : []);
  // Each item normalized to: { id, severity, title, resource, type, description, evidence, remediation }
}
```

### Step 3: Merge and Dedup

```typescript
// MCP findings + chat findings merged, deduped by id
const seen = new Set<string>();
const merged: Finding[] = [];
for (const f of [...mcpFindings, ...chatFindings]) {
  if (!seen.has(f.id)) {
    seen.add(f.id);
    merged.push(f);
  }
}
```

### Step 4: Frontend Rendering

```typescript
// findings-view.tsx — custom renderer, NOT BrickViewRenderer

// 1. Summary bar: total count + severity filter pills
// SEV_ORDER: ["critical", "high", "medium", "low", "info"]
// SEV_COLORS: critical=red, high=orange, medium=yellow, low=blue, info=gray
// Click pill → toggle filter, ring highlight on active

// 2. Sorted display: always severity-ordered (critical first)
const sorted = [...filtered].sort(
  (a, b) => SEV_ORDER.indexOf(a.severity) - SEV_ORDER.indexOf(b.severity)
);

// 3. Each finding row:
//    [severity pill] [title ...] [resource] [chevron ▸]
//    Click → expand with AnimatePresence → FindingDetail component

// 4. Empty state: Shield icon + "No findings yet. Run a security scan..."
```

### Step 5: Triggering Findings (Agent Session)

```python
# During a live agent session, the agent calls security tools:
security_run_analysis(target="arn:aws:lambda:us-east-1:123456:function:AuthHandler")
# → Result includes findings array that flows through AG-UI toolCalls

# Or via posture check:
security_check_posture(scope="production")
# → Result with findings extracted by useFindings hook
```

## Known Limitations

- Findings only populate during live agent sessions (CopilotKit state bridge)
- `security_security.list_analyses` may return empty if no prior scans persisted
- The `useFindings` hook is reactive — new tool calls appear in real-time
- No manual refresh button; data flows automatically from AG-UI events

## Success Criteria

- [ ] Severity filter pills show counts and toggle filtering
- [ ] Findings sorted by severity (critical → info)
- [ ] Expand/collapse animates smoothly via AnimatePresence
- [ ] FindingDetail shows description, evidence, remediation
- [ ] Dual data merge: persisted MCP analyses + live tool call results
- [ ] Empty state renders when no findings exist
- [ ] Security tool pattern matching catches `security_*`, `posture`, `threat`, `vulnerability`, `scan`

## API Reference

| Tool / Hook | Source | Key Args | Returns |
|-------------|--------|----------|---------|
| `security_security.list_analyses` | MCP (on mount) | — | `{analyses: [{analysis_id, findings: [...]}]}` |
| `useFindings(toolCalls)` | React hook | `ActiveToolCall[]` | `Finding[]` (merged, deduped) |
| AG-UI `TOOL_CALL_END` + `TOOL_CALL_RESULT` | SSE event pair | — | END closes the tool span; RESULT carries the `content` JSON and creates the `role:"tool"` message the FE reducer reads (AG-UI v0.0.47, see [`a2ui-protocol.md`](../steering/a2ui-protocol.md#tool-call-lifecycle-the-end--result-pair-ag-ui-v0047)) |
| `FindingDetail` | Component | `finding: Finding` | Expanded detail panel |
