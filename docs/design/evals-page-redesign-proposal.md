# Evals Page Redesign Proposal

**Status:** Draft — for meta-architect review  
**Author:** UX Designer Agent  
**Date:** 2026-03-20

---

## The Problem, Precisely

The current evals page answers the wrong question. It shows *what tools exist* (12 evaluator cards) instead of *what happened* (run results). A security engineer opening this page sees:

```
output          OUTPUT_LEVEL  —
helpfulness     TRACE_LEVEL   —
faithfulness    TRACE_LEVEL   —
...
```

Every row has a dash for its value. There is no timestamp, no score, no verdict, no agent identity. The page is a capability catalog, not a results dashboard. It's the equivalent of a CI/CD page that shows "we have a test runner" instead of showing the last build.

---

## What Users Actually Need (Ranked)

1. **Did the last eval pass or fail?** — the single most important signal
2. **What was the score?** — 0.87 means something; "output" does not
3. **What was being tested?** — input text, truncated
4. **Who judged it?** — "Helpfulness" not "TRACE_LEVEL"
5. **Why did it pass/fail?** — the reason string from the evaluator
6. **What agent ran?** — model_id, system prompt snippet
7. **When?** — timestamp, relative ("2 hours ago")
8. **Tool calls?** — name, latency, result (for TRACE_LEVEL evaluators)

---

## Critical Data Gap: Results Are Ephemeral

`evals_run_experiment` returns results but **does not persist them**. The tool returns:

```json
{
  "name": "experiment",
  "case_results": [
    {"case_name": "...", "score": 0.87, "passed": true, "reason": "..."}
  ],
  "summary": {"overall_score": 0.87, "pass_rate": 1.0, "total_cases": 2},
  "evaluators_used": ["helpfulness"]
}
```

This data evaporates after the tool call. The UI can never show it because it was never stored.

### Persistence Proposal

Add a new `evals_list_run_results` tool backed by a simple JSON store in `.object_store/eval_runs/`. When `evals_run_experiment` completes, it should write a result file alongside the experiment config. The schema:

```json
{
  "run_id": "uuid",
  "experiment_name": "security-eval-001",
  "timestamp": "2026-03-20T22:00:00Z",
  "agent": {
    "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
    "system_prompt_snippet": "You are a security analyst..."
  },
  "evaluators_used": ["helpfulness", "faithfulness"],
  "summary": {
    "pass_rate": 0.85,
    "avg_score": 0.82,
    "total_cases": 2,
    "passed": 1,
    "failed": 1,
    "duration_ms": 4200
  },
  "case_results": [
    {
      "case_name": "lambda-security-posture",
      "input_snippet": "Analyze the security posture of a Lambda function...",
      "output_snippet": "The Lambda function has several security concerns...",
      "score": 0.91,
      "passed": true,
      "reason": "Response identifies specific risks with actionable remediation",
      "evaluator": "helpfulness",
      "tool_calls": []
    }
  ]
}
```

Two new MCP tools needed:
- `evals_list_run_results` — list all persisted runs (filename, timestamp, pass_rate, case_count)
- `evals_get_run_result(run_id)` — load a specific run's full case results

This is a backend change in `components/evals/runtime/` — out of scope for the view redesign but **must be filed as a dependency**.

---

## Page Architecture: Three Tabs

The redesigned page uses a `tabs` component with three tabs. This replaces the current flat three-section layout which forces users to scroll past the evaluator catalog to reach anything useful.

```
┌─────────────────────────────────────────────────────────┐
│  🧪  Evaluations                                        │
│  Agent quality benchmarking · 12 judges · 4 experiments │
│  gradient: from-violet-600 to-purple-700                │
└─────────────────────────────────────────────────────────┘

Zone 2 (metrics row):
  [Last Run: PASS]  [Pass Rate: 85%]  [Avg Score: 0.82]  [Runs: 4]

Zone 3 (tabs):
  [ Run Results ] [ Experiments ] [ Evaluators ]
```

**Tab 1 is the default.** Users land on results, not a catalog.

---

## Section 1: Run Results Tab (Primary — default active)

### What it shows
- All persisted eval runs, newest first
- Per-run: timestamp, experiment name, pass/fail badge, pass rate %, avg score bar, evaluators used
- Expandable per-case rows: input snippet, output snippet, score ring, reason text, evaluator name in plain English

### Component pattern

**Summary row per run** — use `item_list` with:
- `status_dot` colored by pass/fail (green/red)
- Title: experiment name + relative timestamp ("security-eval-001 · 2h ago")
- Badge: "PASS" (green) or "FAIL" (red)
- Inline sparkline: per-case scores as a mini bar chart
- `trend_badge`: pass rate % with up/down arrow vs previous run

**Expanded detail** — `detail_panel` with:
- Agent card: model_id (truncated), system prompt first 80 chars
- Per-case table with columns: Case, Input (truncated 60 chars), Score (visual bar), Verdict, Judge, Reason

### Score visualization

Score 0–1 rendered as a horizontal progress bar with color:
- 0.0–0.5: red (`intent: critical`)
- 0.5–0.8: amber (`intent: warning`)  
- 0.8–1.0: green (`intent: success`)

Use the existing `progress` component — it already supports `value`, `max`, `intent`.

### Plain-English evaluator names

Map internal names to human labels in the view data:

| Internal | Display |
|----------|---------|
| `output` | Custom Rubric |
| `helpfulness` | Helpfulness |
| `faithfulness` | Factual Accuracy |
| `tool_selection` | Tool Choice |
| `tool_parameter` | Tool Parameters |
| `trajectory` | Action Sequence |
| `interactions` | Conversation Quality |
| `goal_success` | Goal Achievement |
| `coherence` | Logical Consistency |
| `conciseness` | Brevity |
| `harmfulness` | Safety Check |
| `response_relevance` | Relevance |

### MCP tool mapping
- `data_tool: "evals_list_run_results"` (new tool — see persistence proposal)
- Drill-down: `evals_get_run_result` with `run_id` from selected item

### 21st.dev component applicability

**Animated Project Cards** (isaiahbjork) — directly applicable. The accordion-style expand/collapse with staggered child animations maps perfectly to per-run rows expanding to show per-case results. The `framer-motion` dependency is already installed. The pattern: collapsed row shows summary (name, badge, sparkline), expanded shows the full case table. The chevron toggle and hover effects are exactly what's needed.

**Glowing Effect** (aceternity) — applicable for the "last run" hero metric card. A subtle border glow on the pass/fail status card draws the eye to the most important signal. The `proximity` glow (activates on hover) adds polish without being distracting. Already uses `motion` which maps to `framer-motion`.

**Loop Animation Hook** (reuno-ui) — not applicable here. It's a generic animation utility hook, not a data display pattern. Skip.

### Implementation in views.py

```python
{
    "id": "evals-run-results",
    "type": "item_list",
    "props": {
        "data_tool": "evals_list_run_results",
        "data_path": "$.runs",
        "item_key": "run_id",
        "empty_icon": "beaker",
        "empty_message": "No eval runs yet. Run an experiment to see results here.",
        "header": {
            "icon": "beaker",
            "stats_tool": "evals_list_run_results",
            "stats_map": {"runs": "$.count"},
        },
        "filters": {
            "field": "verdict",
            "values": ["PASS", "FAIL"],
            "colors": {"PASS": "emerald", "FAIL": "red"},
            "show_counts": True,
        },
        "item_layout": {
            "status_dot": {
                "value_path": "$.verdict",
                "states": {"PASS": "emerald", "FAIL": "red"},
            },
            "title": "$.experiment_name",
            "subtitle": "$.timestamp_relative",
            "badge": {"field": "verdict", "color_map": "filters.colors"},
            "sparkline": {"data_path": "$.case_scores", "type": "bar"},
            "trend_badge": {"value_path": "$.pass_rate", "suffix": "%"},
        },
        "detail": {
            "metadata": [
                {"label": "Model", "path": "$.agent.model_id"},
                {"label": "System Prompt", "path": "$.agent.system_prompt_snippet"},
                {"label": "Evaluators", "path": "$.evaluators_used"},
                {"label": "Duration", "path": "$.summary.duration_ms", "suffix": "ms"},
            ],
            "tabs": [
                {
                    "id": "cases",
                    "label": "Case Results",
                    "tool": "evals_get_run_result",
                    "args": {"run_id": "$.run_id"},
                    "render_as": "table",
                    "columns": [
                        {"key": "case_name", "label": "Case"},
                        {"key": "input_snippet", "label": "Input"},
                        {"key": "score", "label": "Score", "type": "progress"},
                        {"key": "passed", "label": "Verdict", "type": "badge"},
                        {"key": "evaluator_display", "label": "Judge"},
                        {"key": "reason", "label": "Reason"},
                    ],
                }
            ],
        },
    },
}
```

---

## Section 2: Experiments Tab

### What it shows
- Saved experiment configs (currently shown as the second section)
- Filename → human name (strip `.json`, replace `-` with spaces, title-case)
- Case count, evaluator list, last run timestamp (if available)
- Action: "Run This Experiment" button that pre-fills the run form

### Component pattern
Same `item_list` pattern as today but with improved labels and a run action.

Key improvements over current:
- Title: "Security Eval 001" not "security-eval-001.json"
- Badge shows evaluator names in plain English, not raw names
- Detail tab shows cases with input text visible (not just count)
- "Run" button in detail panel triggers `evals_run_experiment` with pre-filled args

### MCP tool mapping
- `data_tool: "evals_list_saved_experiments"` (existing)
- Detail: `evals_load_experiment` (existing)

---

## Section 3: Evaluators Tab

### What it shows
The current evaluator catalog — but demoted to tab 3 since it's reference material, not the primary use case.

Key improvements:
- Remove "TRACE_LEVEL", "OUTPUT_LEVEL", "SESSION_LEVEL" from badges
- Replace with plain-English level labels: "Per-Response", "Per-Turn", "Per-Session"
- Add "Needs rubric" indicator only where `requires_rubric: true`
- Group by level with visual separators

### Component pattern
Same `item_list` with filter pills, but with relabeled filter values:

```python
"filters": {
    "field": "level",
    "values": ["OUTPUT_LEVEL", "TRACE_LEVEL", "SESSION_LEVEL"],
    "labels": {
        "OUTPUT_LEVEL": "Per-Response",
        "TRACE_LEVEL": "Per-Turn",
        "SESSION_LEVEL": "Per-Session",
    },
    "colors": {
        "OUTPUT_LEVEL": "purple",
        "TRACE_LEVEL": "blue",
        "SESSION_LEVEL": "emerald",
    },
    "show_counts": True,
},
```

---

## Zone 2: Summary Metrics

Four metrics in the info zone, populated from `evals_list_run_results`:

```python
{"id": "evals-metric-verdict", "type": "metric", "props": {
    "zone": "info", "label": "Last Run",
    "value": "—", "icon": "check-circle",
    "intent": "hero",
    "data_tool": "evals_list_run_results",
    "data_path": "$.latest.verdict",
    "tooltip": "Pass/fail verdict of the most recent eval run",
}},
{"id": "evals-metric-pass-rate", "type": "metric", "props": {
    "zone": "info", "label": "Pass Rate",
    "value": "—", "icon": "chart-bar",
    "intent": "success",
    "data_tool": "evals_list_run_results",
    "data_path": "$.latest.summary.pass_rate",
    "tooltip": "Percentage of cases that passed in the last run",
}},
{"id": "evals-metric-avg-score", "type": "metric", "props": {
    "zone": "info", "label": "Avg Score",
    "value": "—", "icon": "star",
    "intent": "default",
    "data_tool": "evals_list_run_results",
    "data_path": "$.latest.summary.avg_score",
    "tooltip": "Average evaluator score (0–1) across all cases",
}},
{"id": "evals-metric-total-runs", "type": "metric", "props": {
    "zone": "info", "label": "Total Runs",
    "value": "—", "icon": "beaker",
    "intent": "muted",
    "data_tool": "evals_list_run_results",
    "data_path": "$.count",
    "tooltip": "Total number of persisted eval runs",
}},
```

---

## Hero Banner

```python
{
    "id": "evals-page",
    "type": "page",
    "props": {
        "title": "Evaluations",
        "subtitle": "Agent quality benchmarking · 12 LLMAJ judges",
        "icon": "🧪",
        "gradient": "from-violet-600 to-purple-700",
        "tooltip": "Run experiments to score agent output with LLM-as-a-Judge evaluators",
    },
}
```

Gradient changed from the default blue to violet/purple — evals is a distinct domain from security (which uses violet/indigo) and metrics (which uses blue). Purple signals "quality assessment."

---

## Run Experiment Form

Moved from the current `views_tabs.py` action pane into a collapsible card in Zone 2 (`zone: "controls"`). This makes it immediately accessible without needing to find an action pane.

Key UX improvements:
- `evaluator_names` field: `select` with multi-select options using plain-English labels
- `model_id` field: pre-populated with the default model
- `experiment_name` field: required, shown first
- Submit label: "Run Experiment" (not "Run")
- After submit: result appears in Run Results tab automatically

---

## What to NOT Change

- The SOP sessions section — it's already well-structured and serves a different workflow (guided multi-phase). Keep it as a fourth tab: "SOP Sessions".
- The `item_list` component pattern — it works well for the experiments and evaluators sections.
- The `views_tabs.py` action builders — they're reusable and well-structured.

---

## Implementation Sequence

1. **Backend first** (blocks everything): Add `evals_list_run_results` and `evals_get_run_result` tools + persistence in `evals_run_experiment`. File as a Beads issue.

2. **View redesign** (can start in parallel with mock data): Rewrite `mcp/views.py` to use the 4-tab structure with the new metric zone.

3. **Plain-English labels**: Add evaluator display name mapping in `views.py` — no backend change needed.

4. **Gradient + hero**: Trivial CSS change in the page props.

---

## 21st.dev Component Assessment Summary

| Component | Verdict | Rationale |
|-----------|---------|-----------|
| Animated Project Cards (isaiahbjork) | **Use** | Accordion expand/collapse with framer-motion stagger is the exact pattern for per-run rows expanding to case results. Already uses lucide-react + framer-motion (both installed). |
| Glowing Effect (aceternity) | **Use selectively** | Apply to the "Last Run" hero metric card only. Proximity glow on hover adds polish. Uses `motion` (framer-motion). Don't apply globally — it would be visually noisy. |
| Loop Animation Hook (reuno-ui) | **Skip** | Generic animation utility, not a data display pattern. No clear mapping to eval results. |
| recharts RadialBarChart | **Use** | Score ring (0–1) for per-case score display. Already installed. `RadialBarChart` with a single bar, colored by score threshold. |
| NumberTicker (Magic UI) | **Use** | Already in codebase. Animate the pass rate % and avg score metrics on load. |
| shadcn Progress | **Use** | Horizontal score bars in the case results table. Already in codebase. |

---

## Files That Need to Change

| File | Change |
|------|--------|
| `components/evals/mcp/views.py` | Full rewrite — 4-tab structure, new metrics, plain-English labels |
| `components/evals/mcp/views_tabs.py` | Add SOP tab builder; update evaluator display names |
| `components/evals/runtime/adapters/strands_adapter.py` | Persist results in `run_experiment()` |
| `components/evals/mcp/experiment_tools.py` | Add `evals_list_run_results`, `evals_get_run_result` tools |
| `components/evals/runtime/ports.py` | Add `RunResult` dataclass |

No changes to `frontends/next-dashboard/` — the renderer already handles all needed component types.

---

## Beads Issues to File

1. **P2**: `evals: persist run results — add evals_list_run_results + evals_get_run_result tools` — blocks the Run Results tab
2. **P3**: `evals: redesign views.py — 4-tab layout, plain-English labels, result-first UX` — depends on #1
3. **P3**: `evals: add run experiment form to Zone 2 controls zone` — can be done independently
