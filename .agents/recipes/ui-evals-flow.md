# Recipe: Evals Page — UI Data Flow

End-to-end data flow from the evals brick MCP tools through the Next.js renderer to the the control-plane runtime dashboard.

## Bricks Used
- `evals` — Suite management, test cases, run tracking

## Scenario

Seed default eval suites, add a custom case, then verify the rendering pipeline: suite list → status dots → case count badges → detail tab run history.

## Prerequisites

- the control-plane runtime gateway running (MCP aggregator available)
- No AWS required (custom backend)

## Steps

### Step 1: Seed Default Suites

```python
result = evals_seed_defaults()
# → {"ok": True, "created": ["qa-accuracy", "safety-guardrails", "tool-usage"], "total": 3}
```

### Step 2: Create a Custom Suite with Cases

```python
suite = evals_create_suite(
    suite_id="ui-regression-v1",
    name="UI Regression Suite",
    description="Validates dashboard rendering correctness",
    cases=[
        {"id": "ui-1", "name": "Empty state render", "input": {"page": "metrics"}, "expected": {"shows_empty": True}},
        {"id": "ui-2", "name": "Filter interaction", "input": {"page": "evals", "filter": "coverage"}, "expected": {"filtered": True}},
    ],
)
# → {"id": "ui-regression-v1", "name": "UI Regression Suite", "case_count": 2}

# Add another case to existing suite
evals_add_case(
    suite_id="ui-regression-v1",
    case_id="ui-3",
    name="Detail expand",
    input_data={"page": "evals", "action": "expand"},
    expected={"detail_visible": True},
)
# → {"added": True, "suite_id": "ui-regression-v1", "total_cases": 3}
```

### Step 3: View Definition Drives the Renderer

```python
views = evals_get_views()
# Returns a single "evals-dashboard" view with one item_list component
```

The view's `props` declare the rendering contract:

```typescript
// renderers-item-list.tsx reads these props:
{
  data_tool: "evals_list_suites",
  data_path: "$.suites",              // extract array from response
  item_key: "id",
  item_layout: {
    status_dot: { value_path: "$.status", states: { completed: "emerald", failed: "red", ... } },
    title: "$.name",
    badge: { field: "case_count", suffix: " cases" },  // "3 cases" badge
  },
  detail: {
    metadata: [
      { label: "Suite ID", path: "$.id" },
      { label: "Test cases", path: "$.case_count" },
      { label: "Description", path: "$.description" },
    ],
    tabs: [
      { id: "runs", label: "Runs", tool: "evals_list_runs", args: { suite_id: "$.id" }, render_as: "list" },
    ],
  }
}
```

### Step 4: Frontend Rendering Pipeline

```typescript
// 1. BrickViewRenderer calls evals_get_views via useToolData
const { data } = useToolData("evals_get_views");
// → normalizeNodes() → ComponentTree → ItemListRenderer

// 2. ItemListRenderer fetches suite list
const { data: rawData } = useToolData("evals_list_suites");
// extractArray(rawData, "$.suites") pulls the array from { suites: [...], count: N }

// 3. Each row renders:
//    - Status dot: maps $.status → color (emerald/red/blue/yellow)
//    - Title: $.name ("QA Accuracy Suite")
//    - Badge: case_count + suffix ("3 cases")

// 4. Expanding a row shows detail panel:
//    - Metadata: Suite ID, case count, description
//    - Runs tab: callTool("evals_list_runs", { suite_id: item.id })
//      render_as: "list" → renders run entries with id, status
```

### Step 5: Verify Data Flow

```python
# List — drives the item rows
suites = evals_list_suites()
# → {"suites": [{"id": "qa-accuracy", "name": "QA Accuracy Suite", "case_count": 3}, ...], "count": 4}

# Detail tab — drives the runs list
runs = evals_list_runs(suite_id="qa-accuracy")
# → {"runs": [{"id": "...", "suite_id": "qa-accuracy", "status": "completed"}], "count": 1}
```

## Success Criteria

- [ ] `evals_seed_defaults` creates 3 default suites
- [ ] `evals_create_suite` adds a custom suite visible in the list
- [ ] `evals_add_case` increments case count on existing suite
- [ ] Suite list renders with status dots and case count badges
- [ ] `data_path: "$.suites"` correctly extracts array from response
- [ ] Detail panel shows metadata (ID, case count, description)
- [ ] Runs tab calls `evals_list_runs` with interpolated `suite_id`

## API Reference

| Tool | Category | Key Args | Returns |
|------|----------|----------|---------|
| `evals_seed_defaults` | operational | — | `{created, skipped, total}` |
| `evals_create_suite` | operational | `suite_id, name, cases` | `{id, name, case_count}` |
| `evals_add_case` | operational | `suite_id, case_id, name, input_data` | `{added, total_cases}` |
| `evals_get_views` | deterministic | — | `[{id, components: [item_list]}]` |
| `evals_list_suites` | deterministic | — | `{suites: [{id, name, case_count}], count}` |
| `evals_list_runs` | deterministic | `suite_id` (optional) | `{runs: [{id, suite_id, status}], count}` |
| `evals_get_run` | deterministic | `run_id` | `{id, suite_id, status, summary, result_count}` |
