# Beautiful Frames Architecture

> Data-driven rich UI: bricks declare what to show, frames decide how it looks.

## Problem Statement

the control-plane runtime has 6 hardcoded canvas panels (`metrics-panel.tsx`, `evals-view.tsx`,
`findings-view.tsx`, `evals-detail.tsx`, `metrics-detail.tsx`, `ml-view.tsx`) that
call MCP tools directly via `callTool()` and contain bespoke layout, filtering,
expand/collapse, status dots, trend arrows, and sparklines. This violates two
core principles:

1. **No bespoke logic in bases** — canvas panels ARE base-level code containing
   brick-specific formatting, tool names, category lists, and color maps.
2. **Views as data** — the rich UX in these panels cannot be expressed by the
   current view component vocabulary (`metric`, `table`, `chart`, `alert`, `tabs`).

The existing `mcp/views.py` declarations are too coarse. A `metric` component shows
a single number card. But `metrics-panel.tsx` shows a *filterable list of metrics*
with per-item status dots, trend arrows, sparklines, category badges, and
expand-to-detail. There is no view component type for that pattern.

**Root cause**: the A2UI/view component catalog lacks "list-of-rich-items" frame
types. Bricks can declare a `table` or a single `metric`, but not a
`metric_list` with status indicators, inline sparklines, and drill-down detail.

---

## Visual Design Constraints

Owner feedback from screenshot review of the current the control-plane runtime MetricsPanel.
These constraints are non-negotiable — every frame component must satisfy them.

### No nesting — flat frames only

The initial design was rejected as "box in a box in a box in a box." Frames
must be FLAT. No card-in-card, no bordered container wrapping another bordered
container. A single visual layer per item. If a frame needs grouping, use
whitespace and subtle dividers — not nested boxes.

### IDE aesthetic is the target

The owner's reference point is the current minimalistic IDE-type theme:
dark background, minimal chrome, VS Code-like layout (activity bar icon rail
on the left, tabbed canvas, collapsible chat sidebar). Frame components must
feel native to this environment — not like a dashboard product or a marketing
page. Think "tool panel in an IDE," not "card grid in a SaaS app."

### Charts and sparklines are the hero elements

"Animated charts can be the focus supported by crisp informative icons." The
visual hierarchy is: **chart/sparkline first**, then icons and badges as
supporting context, then text last. Frame layouts must give charts the most
visual weight. Text labels, status dots, and category pills are secondary —
they support the chart, not the other way around.

### MetricsPanel is the reference implementation

The existing `metrics-panel.tsx` screenshot establishes the design language
that frames must match:

- **Flat single-row items** — no cards, no borders, no box-in-box nesting.
  Each metric is one horizontal row: status dot + name + brick icon +
  category pill on the left, value + trend arrow + chevron on the right.
- **Inline indicators** — all status information lives on the same line as
  the item name. Nothing wraps, nothing stacks vertically within a row.
- **Minimal chrome** — no heavy containers, no shadows, no rounded card
  borders. The only border is a subtle `border-border/50` on the row button.
  Background is `bg-card/30` — barely visible.
- **Expand-in-place** — detail is a subtle metadata line below the row
  (e.g., `Warning: 70  Critical: 50  Source: graph  Domain: platform
  Format: percent`), not a separate panel, modal, or bordered card.
- **Compact header** — icon + stat text like `8 definitions · 0 data points`.
  No title bar, no description paragraph, no extra padding.
- **Filter pills** — small colored pills top-right for category filtering
  (`all` / `coverage` / `risk` / `quality` / `performance`). 10px font,
  rounded-full, color-coded per category.

### Agent-driven, not hardcoded

The entire point of beautiful frames is that agents (Kiro, chat agent, any
MCP client) drive what's displayed. Hardcoded `callTool()` invocations in
React components defeat the purpose of AG-UI and A2UI. Frame components
accept data declarations — they never decide which tools to call or what
categories exist. That knowledge lives in the brick's `mcp/views.py`.

### Frames ARE the rendering layer

The "Path 1 (enrich hints) vs Path 2 (accept hybrid)" framing was rejected
as uncreative. The correct mental model: beautiful frames are the universal
rendering layer. Any data — from any brick, any agent, any MCP tool — flows
through them. There is no "hardcoded path" vs "data-driven path." There is
only the frame, and the data that fills it.

---

## 1. New Frame Component Types

Six new component types added to the view vocabulary. Each is a "beautiful frame" —
a pre-built React component with all animations/polish baked in, accepting only data.

### 1.1 `item_list` — The Universal Rich List Frame

The core frame. Replaces `metrics-panel.tsx`, `evals-view.tsx`, `ml-view.tsx`.

> **Rendering constraint**: This frame MUST render as flat single-row items
> matching the IDE aesthetic from the MetricsPanel screenshot — NOT as card
> grids, bordered tiles, or nested containers. Each item is one horizontal
> line: status dot + name + icon + category pill | value + trend + chevron.
> The expand detail is a subtle inline metadata line below the row (key-value
> pairs on a single line, no border, no card wrapper), not a bordered panel
> or modal. See [Visual Design Constraints](#visual-design-constraints).

```python
{
    "type": "item_list",
    "props": {
        "data_tool": "metrics_get_registry",       # tool that returns the item array
        "item_key": "id",                           # unique key field per item
        "empty_icon": "chart-bar-square",           # Heroicons name for empty state
        "empty_message": "No metrics tracked yet.",
        "header": {                                 # optional summary bar
            "icon": "chart-bar",
            "stats_tool": "metrics_health_check",   # tool for header stats
            "stats_map": {                          # extract stats from tool result
                "definitions": "$.definitions",
                "data points": "$.store.total_points",
            },
        },
        "filters": {                                # category filter pills
            "field": "category",
            "values": ["coverage", "risk", "quality", "performance"],
            "colors": {                             # per-value color tokens
                "coverage": "blue",
                "risk": "orange",
                "quality": "emerald",
                "performance": "purple",
            },
        },
        "item_layout": {                            # how each row renders
            "status_dot": {                         # colored dot from thresholds
                "value_path": "$.snapshot.current_value",
                "thresholds": {"warning": "$.thresholds.warning",
                               "critical": "$.thresholds.critical"},
            },
            "title": "$.name",
            "subtitle_icon": "$.source_brick",      # small icon from field
            "badge": {"field": "category", "color_map": "filters.colors"},
            "value": {
                "path": "$.snapshot.current_value",
                "format": "$.format",
            },
            "trend": {
                "direction": "$.snapshot.trend",
                "change_pct": "$.snapshot.change_pct",
            },
            "secondary_icon": {                     # e.g. clock icon when data exists
                "icon": "clock",
                "visible_when": "$.snapshot.data_points > 0",
                "tooltip": "$.snapshot.data_points + ' data points'",
            },
        },
        "item_snapshot_tool": "metrics_get_snapshot",  # per-item detail fetch
        "item_snapshot_args": {"metric_id": "$.id"},    # args template
        "snapshot_merge_path": "snapshot",               # merge result here

        "detail": {                                 # expand/collapse detail panel
            "sparkline": {
                "data_path": "$.snapshot.data_points",
                "color": "indigo",
                "height": 32,
                "max_points": 20,
            },
            "metadata": [                           # key-value pairs in detail
                {"label": "Warning", "path": "$.thresholds.warning"},
                {"label": "Critical", "path": "$.thresholds.critical"},
                {"label": "Source", "path": "$.source_brick"},
                {"label": "Domain", "path": "$.domain"},
                {"label": "Format", "path": "$.format"},
            ],
        },
    },
}
```

The `$.*` paths are JSONPath-lite expressions resolved against each item object.
The renderer walks the item_layout spec and maps each slot to the appropriate
visual element (status dot, trend arrow, badge, etc.) — all with framer-motion
animations baked into the frame component.

### 1.2 `status_dot` — Threshold-Based Status Indicator

Inline component. Renders a colored dot based on value vs thresholds.

```python
{"type": "status_dot", "props": {
    "value": 85.0,
    "thresholds": {"good": 80, "warning": 60, "critical": 40},
    "colors": {"good": "emerald", "warning": "yellow", "critical": "red", "unknown": "gray"},
}}
```

### 1.3 `trend_badge` — Direction + Percentage Change

Inline component. Arrow + optional percentage.

```python
{"type": "trend_badge", "props": {
    "direction": "up",       # "up" | "down" | "flat"
    "change_pct": 12.5,      # optional
    "positive_is_good": True, # controls color semantics
}}
```

### 1.4 `sparkline` — Inline Mini Chart

Renders a tiny bar or line chart from an array of numbers.

```python
{"type": "sparkline", "props": {
    "data": [10, 15, 12, 18, 22, 19, 25],
    "variant": "bar",        # "bar" | "line"
    "color": "indigo",
    "height": 32,
    "max_points": 20,        # truncate to last N
}}
```

### 1.5 `detail_panel` — Animated Expand/Collapse

Container that animates open/closed. Used as the detail view inside `item_list`.

```python
{"type": "detail_panel", "props": {
    "sparkline": {"data_path": "$.data_points", "color": "indigo"},
    "metadata": [
        {"label": "Source", "value": "graph"},
        {"label": "Domain", "value": "security"},
    ],
}}
```

### 1.6 `filter_bar` — Category Filter Pills

Horizontal pill bar for filtering. Used standalone or embedded in `item_list`.

```python
{"type": "filter_bar", "props": {
    "field": "severity",
    "values": ["critical", "high", "medium", "low", "info"],
    "colors": {"critical": "red", "high": "orange", "medium": "yellow",
               "low": "blue", "info": "gray"},
    "show_counts": True,
}}
```

### Component Type Summary

| Type | Purpose | Replaces |
|------|---------|----------|
| `item_list` | Rich filterable list with detail drill-down | metrics-panel, evals-view, ml-view |
| `status_dot` | Threshold-based colored indicator | Inline in metrics-panel |
| `trend_badge` | Direction arrow + change % | Inline in metrics-panel |
| `sparkline` | Mini inline chart | MetricDetail sparkline |
| `detail_panel` | Animated expand/collapse container | MetricDetail, EvalsDetail, FindingDetail |
| `filter_bar` | Category filter pills | Filter buttons in metrics-panel, findings-view |

These 6 types plus the existing vocabulary (`page`, `metric`, `chart`, `table`,
`tabs`, `form`, `alert`, `action_pane`) cover 100% of the UX in the hardcoded panels.

---

## 2. Before/After View Declaration

### BEFORE: Current `metrics/mcp/views.py`

The current declaration uses `metric` (single number cards), `chart`, `alert`,
`tabs`, `form`, and `action_pane`. It cannot express:
- A list of all metrics with per-item status dots, trend arrows, sparklines
- Category filter pills (coverage/risk/quality/performance)
- Per-metric expand/collapse with sparkline + metadata
- Per-metric snapshot fetching (needs `metric_id` argument)
- Header bar with aggregated stats (definition count, data point count)

So `metrics-panel.tsx` was built as a bespoke 160-line React component that
hardcodes `callTool("metrics_get_registry")`, `callTool("metrics_get_snapshot",
{metric_id})`, category arrays, color maps, and the entire layout.

### AFTER: New `metrics/mcp/views.py` using `item_list` frame

```python
def _children() -> list[dict[str, Any]]:
    return [
        # ── Zone 1: The metrics list (replaces entire metrics-panel.tsx) ──
        {
            "id": "metrics-list",
            "type": "item_list",
            "props": {
                "zone": "output",
                "data_tool": "metrics_get_registry",
                "item_key": "id",
                "empty_icon": "chart-bar-square",
                "empty_message": "No metrics tracked yet. The agent records "
                    "metrics during security scans and evaluations.",
                "header": {
                    "icon": "chart-bar",
                    "stats_tool": "metrics_health_check",
                    "stats_map": {
                        "definitions": "$.definitions",
                        "data points": "$.store.total_points",
                    },
                },
                "filters": {
                    "field": "category",
                    "values": ["coverage", "risk", "quality", "performance"],
                    "colors": {
                        "coverage": "blue", "risk": "orange",
                        "quality": "emerald", "performance": "purple",
                    },
                },
                "item_layout": {
                    "status_dot": {
                        "value_path": "$.snapshot.current_value",
                        "thresholds": {
                            "warning": "$.thresholds.warning",
                            "critical": "$.thresholds.critical",
                        },
                    },
                    "title": "$.name",
                    "subtitle_icon": "$.source_brick",
                    "badge": {"field": "category", "color_map": "filters.colors"},
                    "value": {
                        "path": "$.snapshot.current_value",
                        "format": "$.format",
                    },
                    "trend": {
                        "direction": "$.snapshot.trend",
                        "change_pct": "$.snapshot.change_pct",
                    },
                },
                "item_snapshot_tool": "metrics_get_snapshot",
                "item_snapshot_args": {"metric_id": "$.id"},
                "snapshot_merge_path": "snapshot",
                "detail": {
                    "sparkline": {
                        "data_path": "$.snapshot.data_points",
                        "color": "indigo",
                        "height": 32,
                        "max_points": 20,
                    },
                    "metadata": [
                        {"label": "Warning", "path": "$.thresholds.warning"},
                        {"label": "Critical", "path": "$.thresholds.critical"},
                        {"label": "Source", "path": "$.source_brick"},
                        {"label": "Domain", "path": "$.domain"},
                        {"label": "Format", "path": "$.format"},
                    ],
                },
            },
        },
        # ── Zone 2: Controls — snapshot query form (unchanged) ──
        {
            "id": "metrics-query-form",
            "type": "form",
            "props": {
                "zone": "controls",
                "tool": "metrics_get_snapshot",
                "title": "Metric Snapshot",
                "submit_label": "Get Snapshot",
                "fields": [
                    {"name": "metric_id", "type": "text",
                     "placeholder": "coverage_score"},
                    {"name": "period", "type": "select",
                     "options": [
                         {"value": "1h", "label": "1 Hour"},
                         {"value": "24h", "label": "24 Hours"},
                         {"value": "7d", "label": "7 Days"},
                     ]},
                ],
            },
        },
        # ── Zone 3: Read-only tabs (unchanged) ──
        metrics_read_tabs(),
        # ── Zone 3: Action pane (unchanged) ──
        {"id": "metrics-actions", "type": "action_pane",
         "props": {"actions": metrics_actions(), "default_action": "record-metric"}},
    ]
```

**What changed**: The three `metric` cards + the entire `metrics-panel.tsx` are
replaced by a single `item_list` declaration. The trend chart and drift alert
are removed from the page-level view (they belong in the per-metric detail or
in the existing tabs). The `item_list` frame handles everything: fetching the
registry, fetching per-item snapshots, filtering, status dots, trends, sparklines,
and expand/collapse — all from this data declaration.

### Evals brick — same pattern

```python
{
    "type": "item_list",
    "props": {
        "data_tool": "evals_list_suites",
        "data_path": "$.suites",           # extract array from result
        "item_key": "id",
        "empty_icon": "beaker",
        "empty_message": "No eval suites yet.",
        "header": {
            "icon": "beaker",
            "stats_tool": "evals_list_runs",
            "stats_map": {"runs": "$.count"},
        },
        "item_layout": {
            "status_dot": {
                "value_tool": "evals_list_runs",
                "value_args": {"suite_id": "$.id"},
                "value_path": "$.runs[0].status",
                "states": {
                    "completed": "emerald", "failed": "red",
                    "running": "blue-pulse", "pending": "yellow",
                },
            },
            "title": "$.name",
            "subtitle_icon_map": {
                "field": "$.id",
                "patterns": {"safety": "shield-check", "tool": "wrench"},
                "default": "beaker",
            },
            "badge": {"field": "case_count", "suffix": " cases"},
        },
        "detail": {
            "detail_tool": "evals_get_suite",
            "detail_args": {"suite_id": "$.id"},
            "sections": [
                {"type": "text", "path": "$.description"},
                {"type": "sub_list",
                 "data_tool": "evals_list_runs",
                 "data_args": {"suite_id": "$.id"},
                 "data_path": "$.runs",
                 "max_items": 5,
                 "item_layout": {
                     "status_dot": {"value_path": "$.status",
                                    "states": {"completed": "emerald",
                                               "failed": "red"}},
                     "title": "$.id",
                     "badge": {"field": "status"},
                 }},
            ],
            "metadata": [
                {"label": "Test cases", "path": "$.case_count", "icon": "beaker"},
                {"label": "Runs", "path": "$.run_count", "icon": "clock"},
            ],
        },
    },
}
```

---

## 3. React Frame Components

### 3.1 New files in `frontends/next-dashboard/components/renderer/`

| File | Component | LOC est. | Purpose |
|------|-----------|----------|---------|
| `renderers-item-list.tsx` | `ItemListRenderer` | ~180 | The main frame: header bar, filter pills, item rows, expand/collapse |
| `renderers-status.tsx` | `StatusDotRenderer`, `TrendBadgeRenderer` | ~60 | Inline status indicators |
| `renderers-sparkline.tsx` | `SparklineRenderer` | ~50 | Mini bar/line chart |
| `renderers-detail-panel.tsx` | `DetailPanelRenderer` | ~80 | Animated expand/collapse with metadata grid |
| `renderers-filter-bar.tsx` | `FilterBarRenderer` | ~50 | Category filter pill strip |

### 3.2 `ItemListRenderer` — the workhorse

This is the "beautiful frame" that replaces `metrics-panel.tsx`, `evals-view.tsx`,
and `ml-view.tsx`. It:

1. Calls `data_tool` via `useToolData` to fetch the item array
2. Optionally calls `header.stats_tool` for summary stats
3. Renders filter pills from `filters` spec
4. For each item, renders a row using `item_layout` spec:
   - `StatusDotRenderer` for the status dot
   - Title text + optional icon
   - Badge with category/count
   - Value + `TrendBadgeRenderer`
   - ChevronRight with rotate animation
5. On expand, renders `DetailPanelRenderer` with:
   - `SparklineRenderer` for inline chart
   - Metadata key-value pairs
6. If `item_snapshot_tool` is specified, fetches per-item data in background
   and merges into item at `snapshot_merge_path`

All framer-motion animations, Lucide icons, shadcn styling, and color tokens
are baked into the frame. The data declaration controls WHAT renders, not HOW.

### 3.3 Component Map additions

```typescript
// In component-map.ts — new entries
import { ItemListRenderer } from "./renderers-item-list";
import { StatusDotRenderer, TrendBadgeRenderer } from "./renderers-status";
import { SparklineRenderer } from "./renderers-sparkline";
import { DetailPanelRenderer } from "./renderers-detail-panel";
import { FilterBarRenderer } from "./renderers-filter-bar";

// Add to COMPONENT_MAP:
item_list: ItemListRenderer,
status_dot: StatusDotRenderer,
trend_badge: TrendBadgeRenderer,
sparkline: SparklineRenderer,
detail_panel: DetailPanelRenderer,
filter_bar: FilterBarRenderer,
```

### 3.4 Key implementation detail: JSONPath-lite resolver

The `item_layout` spec uses `$.field.path` expressions. The renderer needs a
tiny resolver function (~15 lines) that walks an object by dot-separated keys:

```typescript
function resolve(obj: Record<string, unknown>, path: string): unknown {
  if (!path.startsWith("$.")) return path; // literal value
  const keys = path.slice(2).split(".");
  let current: unknown = obj;
  for (const key of keys) {
    if (current == null || typeof current !== "object") return undefined;
    current = (current as Record<string, unknown>)[key];
  }
  return current;
}
```

This is NOT a full JSONPath implementation. It handles `$.foo.bar.baz` only —
no array indexing, no filters, no wildcards. Simple and sufficient.

---

## 4. Data Flow

Four mechanisms exist for getting data into frames. The `item_list` frame uses
all four depending on context:

### 4.1 `data_tool` prop (primary — brick-declared, renderer-fetched)

```
Brick declares:  {"data_tool": "metrics_get_registry"}
Renderer calls:  useToolData("metrics_get_registry")
Result flows:    tool result → items array → item_layout mapping → rendered rows
```

This is the default path. The brick says WHICH tool, the renderer calls it.
Already works today — `useToolData` hook exists and `ChartRenderer` uses it.

### 4.2 `item_snapshot_tool` (per-item enrichment)

```
Brick declares:  {"item_snapshot_tool": "metrics_get_snapshot",
                  "item_snapshot_args": {"metric_id": "$.id"}}
Renderer calls:  useToolData("metrics_get_snapshot", {metric_id: item.id})
                 for each item, in background after initial render
Result flows:    snapshot merged into item at snapshot_merge_path
```

This solves the N+1 problem elegantly: the list renders immediately from the
registry data, then enriches each item with snapshot data in the background.
The renderer batches these calls and updates state progressively.

### 4.3 AG-UI `STATE_DELTA` (agent-pushed live updates)

```
Agent emits:     STATE_DELTA {op: "replace", path: "/metrics/0/snapshot/current_value", value: 92}
SSE stream:      → the control-plane runtime chat sidebar → canvas state
Renderer reads:  useCopilotCanvasState() provides live state
```

For real-time agent-driven updates. The agent pushes JSON Patch deltas via
AG-UI SSE, and the canvas state updates. The `item_list` frame can optionally
subscribe to a state path for live data instead of (or in addition to) tool polling.

Add an optional prop:

```python
"live_state_path": "metrics"  # reads from AG-UI state at this key
```

### 4.4 A2UI payloads (agent emits full component trees)

```
Agent emits:     A2UIPayload with item_list components
ui_render_a2ui:  validates + converts to ReactAdapter JSON
Renderer:        ComponentRenderer handles it like any view
```

For cases where an agent wants to push a completely custom item list (e.g.,
during a scan, the agent builds a findings list incrementally). The agent
emits A2UI payloads with `item_list` type components, and the existing
A2UI → ReactAdapter → ComponentRenderer pipeline handles it.

### Data flow summary

| Mechanism | Who initiates | Latency | Use case |
|-----------|--------------|---------|----------|
| `data_tool` | Renderer (on mount) | One-shot | Initial data load |
| `item_snapshot_tool` | Renderer (background) | Progressive | Per-item enrichment |
| `STATE_DELTA` | Agent (push) | Real-time | Live updates during agent work |
| A2UI payload | Agent (push) | Real-time | Agent-constructed custom views |

---

## 5. Solving Bead python-factory-7b2

### The problem

The Trends tab declares `"lazy_tool": "metrics_get_trend"` and the Drift tab
declares `"lazy_tool": "metrics_detect_drift"`. Both tools REQUIRE a `metric_id`
argument. But `LazyTabContent` calls `callTool(tab.lazy_tool)` with NO arguments.
The tools fail silently or return empty results.

### Why this happened

The tab system has no concept of "context from a selected item." Tabs are
declared statically in `views_tabs.py` with a single `lazy_tool` name. There's
no way to say "call this tool with the metric_id of whatever metric the user
selected in the list above."

### How `item_list` fixes it

With the new architecture, Trends and Drift are NOT top-level tabs. They belong
in the per-metric `detail` panel:

```python
"detail": {
    "sparkline": {
        "data_path": "$.snapshot.data_points",
        "color": "indigo",
    },
    "tabs": [
        {
            "id": "trend",
            "label": "Trend",
            "tool": "metrics_get_trend",
            "args": {"metric_id": "$.id", "window": "7d", "buckets": 20},
            "render_as": "chart",
            "chart_props": {
                "chart_type": "line",
                "x_key": "start",
                "y_key": "value",
                "color": "indigo",
                "height": 160,
            },
        },
        {
            "id": "drift",
            "label": "Drift",
            "tool": "metrics_detect_drift",
            "args": {"metric_id": "$.id"},
            "render_as": "alert",
            "alert_props": {
                "intent_field": "drifted",
                "intent_map": {"true": "warning", "false": "success"},
            },
        },
    ],
    "metadata": [
        {"label": "Warning", "path": "$.thresholds.warning"},
        {"label": "Critical", "path": "$.thresholds.critical"},
        {"label": "Source", "path": "$.source_brick"},
    ],
}
```

`colors` and `intent_map` keys must match the serialized field value exactly:
the strict output model only accepts string keys, and the renderer's
`Record<string, string>` lookup is case-exact. Booleans therefore arrive as the
lowercase strings `"true"`/`"false"` — a Python `True` key serializes to
`"True"` and matches neither.

The `detail.tabs` array declares per-item tabs. When the user expands a metric
and clicks the "Trend" tab, the `DetailPanelRenderer` calls
`metrics_get_trend({metric_id: "coverage_score"})` — with the actual metric ID
from the parent item context. The `$.id` expression resolves against the
expanded item.

This is the key insight: **context flows from item to detail**. The `item_list`
frame knows which item is expanded and passes it as the resolution context for
all `$.*` expressions in the detail spec.

### What changes in `views_tabs.py`

The Trends and Drift tabs are REMOVED from the top-level `metrics_read_tabs()`.
They move into the `item_list.detail.tabs` spec in `views.py`. The remaining
top-level tabs (Registry, Snapshots, Taxonomy) stay — they don't
need a `metric_id`.

```python
def metrics_read_tabs() -> dict[str, Any]:
    return {
        "id": "metrics-read-tabs",
        "type": "tabs",
        "props": {
            "tabs": [
                {"id": "registry", "label": "Registry",
                 "lazy_tool": "metrics_get_registry",
                 "result_hints": {"searchable": True, "sortable": True}},
                {"id": "snapshots", "label": "Snapshots",
                 "lazy_tool": "metrics_get_registry",
                 "result_hints": {"prefer": "stat_grid"}},
                # REMOVED: trends (now in item_list detail)
                # REMOVED: drift  (now in item_list detail)
                {"id": "taxonomy", "label": "Taxonomy",
                 "lazy_tool": "metrics_get_by_taxonomy",
                 "result_hints": {"prefer": "grouped_table",
                                  "group_by": "domain",
                                  "columns": [...]}},
            ],
        },
    }
```

---

## 6. Migration Path

Step-by-step migration from hardcoded panels to data-driven rendering.
Each step is independently shippable with no visual regression.

### Phase 1: Build the frame components (no view changes yet)

1. Create `renderers-item-list.tsx` — the `ItemListRenderer` component
2. Create `renderers-status.tsx` — `StatusDotRenderer`, `TrendBadgeRenderer`
3. Create `renderers-sparkline.tsx` — `SparklineRenderer`
4. Create `renderers-detail-panel.tsx` — `DetailPanelRenderer`
5. Create `renderers-filter-bar.tsx` — `FilterBarRenderer`
6. Add all 6 to `component-map.ts` and `renderers.tsx` barrel
7. Add types to `renderer-types.ts` (ItemListProps, etc.)

**Test**: Create a test page that renders an `item_list` node with hardcoded
props matching the metrics-panel data shape. Visually compare side-by-side.

### Phase 2: Update Python view declarations

8. Update `components/metrics/mcp/views.py` — replace `_children()` with
   `item_list` declaration (as shown in Section 2)
9. Update `components/metrics/mcp/views_tabs.py` — remove Trends/Drift tabs
10. Add `item_list`, `status_dot`, `trend_badge`, `sparkline`, `detail_panel`,
    `filter_bar` to A2UI component catalog (`components/ui/runtime/a2ui/components.py`)
11. Add the same types to `ComponentType` enum in `components/ui/runtime/models.py`

**Test**: Call `metrics_get_views` via MCP, verify the response contains the
`item_list` component with all expected props.

### Phase 3: Wire canvas to use data-driven rendering

12. In `canvas.tsx`, replace the hardcoded `EvalsView` import with a generic
    `BrickViewRenderer` that calls `*_get_views()` and renders via `ComponentTree`
13. Same for the Metrics sub-tab inside EvalsView
14. Same for `MLView`

The `BrickViewRenderer` pattern:

```typescript
function BrickViewRenderer({ viewTool }: { viewTool: string }) {
  const { data, loading } = useToolData(viewTool);
  if (loading) return <CanvasLoader />;
  const views = (data as { id: string; components: ReactAdapterNode[] }[]) ?? [];
  const nodes = views[0]?.components ?? [];
  return <ComponentTree nodes={nodes} />;
}

// In canvas.tsx:
{props.activeView === "evals" && <BrickViewRenderer viewTool="evals_get_views" />}
{props.activeView === "ml" && <BrickViewRenderer viewTool="ml_get_views" />}
```

**Test**: Navigate to Evals tab, verify it renders identically to the old
hardcoded panel. Toggle between metrics and evals sub-views.

### Phase 4: Delete hardcoded panels

15. Delete `canvas/metrics-panel.tsx`
16. Delete `canvas/metrics-detail.tsx`
17. Delete `canvas/evals-view.tsx`
18. Delete `canvas/evals-detail.tsx`
19. Delete `canvas/ml-view.tsx`
20. Update `canvas.tsx` imports — remove lazy imports for deleted files

**Test**: Full visual regression test. Every view that existed before must
render with equivalent UX through the data-driven pipeline.

### Phase 5: Findings view (different pattern)

Findings are NOT fetched via MCP tool — they're extracted from AG-UI tool call
results in the chat stream (`useFindings` hook). This is a different data source.

21. Add a `live_data_path` prop to `item_list` that reads from AG-UI canvas state
    instead of calling a tool
22. Update findings view declaration (in the graph or security brick) to use
    `item_list` with `live_data_path: "findings"`
23. Delete `canvas/findings-view.tsx` and `canvas/finding-detail.tsx`

This is Phase 5 because it requires the AG-UI state integration, which is
more complex than the tool-based data flow.

---

## 7. File-Level Changes

### Python side (components/)

| File | Action | What changes |
|------|--------|-------------|
| `components/ui/src/factory/ui/runtime/a2ui/components.py` | MODIFY | Add 6 new `ComponentSpec` entries: `ItemList`, `StatusDot`, `TrendBadge`, `Sparkline`, `DetailPanel`, `FilterBar` |
| `components/ui/src/factory/ui/runtime/models.py` | MODIFY | Add 6 new values to `ComponentType` enum |
| `components/metrics/src/factory/metrics/mcp/views.py` | MODIFY | Replace `_children()` — remove 3 metric cards + chart + alert, add 1 `item_list` |
| `components/metrics/src/factory/metrics/mcp/views_tabs.py` | MODIFY | Remove Trends and Drift tabs from `metrics_read_tabs()` |
| `components/evals/src/factory/evals/mcp/views.py` | MODIFY | Add `item_list` declaration for eval suites (if views exist; otherwise CREATE) |
| `components/machine_learning/src/factory/machine_learning/mcp/views.py` | MODIFY | Add `item_list` declaration for experiments |

### Next.js side (frontends/next-dashboard/)

| File | Action | What changes |
|------|--------|-------------|
| `components/renderer/renderers-item-list.tsx` | CREATE | `ItemListRenderer` — the main frame (~180 LOC) |
| `components/renderer/renderers-status.tsx` | CREATE | `StatusDotRenderer` + `TrendBadgeRenderer` (~60 LOC) |
| `components/renderer/renderers-sparkline.tsx` | CREATE | `SparklineRenderer` (~50 LOC) |
| `components/renderer/renderers-detail-panel.tsx` | CREATE | `DetailPanelRenderer` with framer-motion (~80 LOC) |
| `components/renderer/renderers-filter-bar.tsx` | CREATE | `FilterBarRenderer` (~50 LOC) |
| `components/renderer/component-map.ts` | MODIFY | Add 6 new entries to `COMPONENT_MAP` |
| `components/renderer/renderers.tsx` | MODIFY | Add barrel exports for 5 new files |
| `components/renderer/renderer-types.ts` | MODIFY | Add `ItemListProps`, `StatusDotProps`, etc. type definitions |
| `components/renderer/use-tool-data.ts` | MODIFY | Add `args` to dependency array (currently ignored in useCallback) |
| `components/canvas/canvas.tsx` | MODIFY | Replace hardcoded view imports with `BrickViewRenderer` |
| `components/canvas/metrics-panel.tsx` | DELETE | Replaced by `item_list` frame |
| `components/canvas/metrics-detail.tsx` | DELETE | Replaced by `detail_panel` frame |
| `components/canvas/evals-view.tsx` | DELETE | Replaced by `item_list` frame |
| `components/canvas/evals-detail.tsx` | DELETE | Replaced by `detail_panel` frame |
| `components/canvas/ml-view.tsx` | DELETE | Replaced by `item_list` frame |
| `components/canvas/findings-view.tsx` | DELETE (Phase 5) | Replaced by `item_list` + `live_data_path` |
| `components/canvas/finding-detail.tsx` | DELETE (Phase 5) | Replaced by `detail_panel` frame |

### File count summary

- **Python**: 6 files modified (0 created, 0 deleted)
- **Next.js**: 5 files created, 4 files modified, 5-7 files deleted
- **Net change**: ~420 LOC of new frame components replace ~650 LOC of hardcoded panels

---

## 8. Design Principles Compliance

| Principle | How this design complies |
|-----------|------------------------|
| Views as data | All rich UX expressed as dicts in `mcp/views.py` |
| No bespoke logic in bases | Canvas panels deleted; renderer is generic |
| <200 LOC per file | Each new renderer file is 50-180 LOC |
| MCP-first | Frame components call tools via `useToolData`, never import bricks |
| Polymorphic/agnostic | New component types added to A2UI catalog; any adapter can render them |
| SRP | Each renderer file handles one frame type |
| No cross-imports | Bricks reference tools by name string, not by import |

## 9. What This Enables

Once frames exist, any agent can drive the UI by:

1. **Declaring views** — a brick's `*_get_views()` returns `item_list` components
2. **Pushing A2UI** — an agent emits `item_list` payloads via `ui_render_a2ui`
3. **Streaming STATE_DELTA** — an agent pushes live metric updates via AG-UI SSE
4. **Composing** — an agent can build a custom dashboard by combining frames:
   metrics `item_list` + findings `item_list` + a `chart` + an `alert`

The beauty is in the FRAME. The data comes from anywhere. An agent that discovers
a new set of metrics can push them into the same gorgeous `item_list` frame
without any frontend changes. That's the "beautiful frames" pattern.

## 10. Open Questions

1. **Pagination**: Should `item_list` support pagination for large lists (100+ items)?
   Recommendation: yes, add optional `page_size` prop. Renderer handles it client-side
   for small lists, server-side (via tool args) for large ones.

2. **Sorting**: Should `item_list` support column sorting? The `filters` prop handles
   category filtering, but sorting by value/name/trend is a separate concern.
   Recommendation: add optional `sort_fields` prop.

3. **Refresh interval**: Should `data_tool` support periodic refresh?
   Recommendation: add optional `refresh_interval_ms` prop to `useToolData`.

4. **Findings data source**: Findings come from AG-UI tool call results, not from
   a brick tool. The `live_data_path` prop (Phase 5) handles this, but the
   exact integration with `useCopilotCanvasState` needs design.
