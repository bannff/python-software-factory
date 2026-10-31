# Recipe: Metrics Page — UI Data Flow

Metrics is subject-focused. Live Runtime Metrics is one `live` focus, never a substitute for durable evidence. All entrants use the same discriminated `MetricFocus` and versioned navigation reference.

## Focus and navigation contract

`MetricFocus` is `Annotated[Union[RunFocus, ExecutionFocus, EvalFocus, TraceFocus, SessionFocus, EntityFocus, LiveFocus, SystemFocus], Field(discriminator="subject_kind")]`; every frozen Pydantic-v2 variant uses `extra="forbid"`. It includes a subject `label`, `requested_availability`, time range, aggregation, and `NavigationRef`. Validation requires: run→`run_id`; execution→`run_id` plus exactly one agent/graph/swarm ID; eval→`eval_ref`; trace→`trace_id` with optional `span_id`; session→`session_id`; entity→`entity_ref`; system/live→no durable subject identity. Compatible optional values narrow with AND semantics; forbidden or contradictory values return actionable `invalid_focus` and never broaden a query.

```ts
NavigationRef = {
  version: "v1";
  surface: "graph" | "timeline" | "evals" | "owner" | "metrics";
  target_ref: string;
  label: string;
  graph_selected_ref?: string;
  graph_context?: BoundedGraphContext;
}
```

**Open metrics** passes `NavigationRef` unchanged. Return restores the originating surface, selected Graph item, and bounded query/neighborhood. **Open related graph** restores the same graph context. An unavailable/unauthorized target renders a disabled named action and explanatory text, never a broken breadcrumb.

## Renderable truth model

`requested_availability` is a request preference. `MetricResult` separately returns `measurement_state`, source class, evidence timestamp or last-updated/completeness, and safe reason/next action.

| State | Required text |
|---|---|
| `live_not_persisted` | Live activity — not persisted |
| `durable_as_of` | Durable measurement — as of `<timestamp>` |
| `still_arriving` | Still arriving; show last update/completeness |
| `no_durable_measurement` | No durable measurement available; show next action |
| `source_unavailable` | Source unavailable |
| `source_deleted` | Source was deleted |
| `source_inaccessible` | Source is inaccessible |

States are text, not color alone; changes announce via an accessible status region. Open/return/graph actions are keyboard-reachable and named. Navigation moves focus to the target heading or restored selected item.

## Sources

Live uses the SSE/browser buffer. Run/execution uses Workflow, retained Telemetry, and Metrics records; eval uses Evals; trace/session uses Telemetry; entity/system uses owner and Metrics aggregates. Telemetry is the only OTLP-to-Metrics materializer; the UI never treats browser counters as durable run measurements.

## Acceptance checks

- [ ] Every entry point preserves the same `NavigationRef`; return restores selected Graph context.
- [ ] Each discriminated focus validates required/forbidden IDs and AND constraints.
- [ ] Each truth state has timestamp/completeness/reason where applicable, textual status, and accessible action behavior.
- [ ] Live-only, no-measurement, arriving, deleted, inaccessible, and durable cases are covered.
