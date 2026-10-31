# Recipe: Evals & Benchmarking

Run LLMAJ evaluations against agent output — from a single direct eval to full SOP workflows.

## Bricks Used
- `evals` — LLMAJ evaluators, experiment management, SOP workflow, UI views

## Prerequisites

- AWS credentials required (Strands LLMAJ evaluators call Bedrock)
- No AWS needed for suite/run CRUD tools (`evals_create_suite`, `evals_list_runs`, etc.)

## Workflows

Three primary patterns, ordered simplest → most structured:

1. **Direct eval** — score pre-existing text with one evaluator
2. **Experiment** — run evaluators against an agent across test cases; save/load configs
3. **SOP** — guided Plan → Data → Eval → Report workflow for thorough benchmarking

---

## Workflow 1: Direct Eval

Score any input/output pair without spinning up an agent.

```python
# Single evaluator — no rubric needed for helpfulness
result = call_brick_tool(
    brick_name="evals",
    tool_name="evals_evaluate",
    arguments='{"input_text": "What is the capital of France?",
                "output_text": "The capital of France is Paris.",
                "evaluator_name": "helpfulness"}'
)
# → {"score": 0.95, "test_pass": true, "reason": "...", "label": "PASS"}

# With a custom rubric (required for "output" evaluator)
result = call_brick_tool(
    brick_name="evals",
    tool_name="evals_evaluate",
    arguments='{"input_text": "Summarize quantum entanglement.",
                "output_text": "...",
                "evaluator_name": "output",
                "rubric": "Response must be accurate, under 3 sentences, and jargon-free."}'
)

# Run multiple evaluators in one call
result = call_brick_tool(
    brick_name="evals",
    tool_name="evals_evaluate_multi",
    arguments='{"input_text": "...", "output_text": "...",
                "evaluator_names": ["helpfulness", "coherence", "harmfulness"]}'
)
# → {"results": [...], "summary": {"avg_score": 0.88, "pass_rate": 1.0}}
```

---

## Workflow 2: Experiment

Run evaluators against an agent across multiple test cases, then save the config for reuse.

### Step 1: Run the experiment

Results are automatically persisted to `.object_store/eval_runs/` and visible in the UI Run Results section.

```python
result = call_brick_tool(
    brick_name="evals",
    tool_name="evals_run_experiment",
    arguments='''{
        "experiment_name": "qa-accuracy-v1",
        "cases": [
            {"name": "Capital of France",
             "input": "What is the capital of France?",
             "expected_output": "Paris"},
            {"name": "Python creator",
             "input": "Who created Python?",
             "expected_output": "Guido van Rossum"}
        ],
        "evaluator_names": ["output"],
        "rubric": "Answer must be factually correct and concise.",
        "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
        "system_prompt": "You are a helpful assistant."
    }'''
)
# → per-case scores + summary report
```

### Step 2: Save the config (appears in UI)

```python
call_brick_tool(
    brick_name="evals",
    tool_name="evals_save_experiment",
    arguments='''{
        "experiment_name": "qa-accuracy-v1",
        "filename": "qa-accuracy-v1.json",
        "cases": [
            {"name": "Capital of France", "input": "What is the capital of France?",
             "expected_output": "Paris"}
        ],
        "evaluator_names": ["output"],
        "rubric": "Answer must be factually correct and concise."
    }'''
)
# Saved to .object_store/qa-accuracy-v1.json — visible in UI "Saved Experiments" section
```

### Step 3: List / reload saved experiments

```python
# List — shown in UI
call_brick_tool(brick_name="evals", tool_name="evals_list_saved_experiments")
# → {"experiments": [{"filename": "qa-accuracy-v1.json", "cases": 1, "size_bytes": 512}], "count": 1}

# Reload
call_brick_tool(
    brick_name="evals",
    tool_name="evals_load_experiment",
    arguments='{"filename": "qa-accuracy-v1.json"}'
)
```

### Auto-generate test cases

```python
call_brick_tool(
    brick_name="evals",
    tool_name="evals_generate_experiment",
    arguments='''{
        "context": "A customer support agent with access to order lookup and refund tools.",
        "task_description": "Handle customer queries about orders and refunds.",
        "num_cases": 5,
        "evaluator_name": "output"
    }'''
)
# → generated cases + rubric ready to pass into evals_run_experiment
```

---

## Workflow 3: SOP (Plan → Data → Eval → Report)

Structured four-phase workflow for thorough agent benchmarking. Each phase advances the session; status is tracked and visible in the UI.

### Phase 1: Plan

```python
plan = call_brick_tool(
    brick_name="evals",
    tool_name="evals_sop_plan",
    arguments='''{
        "agent_description": "A coding assistant that writes and reviews Python code.",
        "agent_tools": ["code_execute", "code_review", "file_write"],
        "evaluation_goals": "Assess code correctness, safety, and helpfulness."
    }'''
)
session_id = plan["session_id"]
# → recommended evaluators, test categories, success criteria
```

### Phase 2: Generate data

```python
call_brick_tool(
    brick_name="evals",
    tool_name="evals_sop_generate_data",
    arguments=f'{{"session_id": "{session_id}", "num_cases": 10, "evaluator_name": "output"}}'
)
```

### Phase 3: Run evaluations

```python
call_brick_tool(
    brick_name="evals",
    tool_name="evals_sop_run",
    arguments=f'{{"session_id": "{session_id}",
                  "model_id": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                  "system_prompt": "You are a Python coding assistant."}}'
)
```

### Phase 4: Report

```python
report = call_brick_tool(
    brick_name="evals",
    tool_name="evals_sop_report",
    arguments=f'{{"session_id": "{session_id}"}}'
)
# → Markdown report: executive summary, per-case results, recommendations

# Check status at any point
call_brick_tool(
    brick_name="evals",
    tool_name="evals_sop_status",
    arguments=f'{{"session_id": "{session_id}"}}'
)

# List all sessions (shown in UI)
call_brick_tool(brick_name="evals", tool_name="evals_sop_list")
```

---

## UI: Three-Section Dashboard

The evals UI (`evals_get_views`) renders three sections:

| Section | Data tool | What it shows |
|---------|-----------|---------------|
| Evaluators catalog | `evals_list_evaluators` | 12 LLMAJ judges, filterable by level (OUTPUT / TRACE / SESSION) |
| Saved experiments | `evals_list_saved_experiments` | Filename, case count, expandable cases tab |
| SOP sessions | `evals_sop_list` | Phase-tracked sessions (plan → data → eval → report) with status dot |

---

## Success Criteria

- [ ] Direct eval returns score, test_pass, and reason
- [ ] Experiment runs against agent and produces per-case scores
- [ ] Saved experiment appears in `evals_list_saved_experiments` and UI
- [ ] SOP session advances through all four phases
- [ ] SOP report contains executive summary and recommendations

---

## MCP Tools

| Tool | Description |
|------|-------------|
| `evals_evaluate` | Score input/output with one LLMAJ evaluator |
| `evals_evaluate_multi` | Score with multiple evaluators; returns aggregate |
| `evals_evaluate_session` | Score with full Strands Session (all 12 evaluators) |
| `evals_run_experiment` | Run evaluators against an agent across test cases |
| `evals_run_simulation` | Multi-turn simulation with ActorSimulator |
| `evals_generate_experiment` | Auto-generate test cases from agent context |
| `evals_save_experiment` | Persist experiment config to `.object_store/` |
| `evals_load_experiment` | Load saved experiment config |
| `evals_list_saved_experiments` | List all saved experiment files |
| `evals_list_evaluators` | List all 12 LLMAJ evaluators with config |
| `evals_sop_plan` | Phase 1: analyze agent, create eval plan |
| `evals_sop_generate_data` | Phase 2: generate test cases |
| `evals_sop_run` | Phase 3: run evaluations |
| `evals_sop_report` | Phase 4: generate Markdown report |
| `evals_sop_status` | Get current SOP session phase |
| `evals_sop_list` | List all SOP sessions |
| `evals_create_suite` | Create a named eval suite |
| `evals_add_case` | Add a test case to a suite |
| `evals_list_suites` | List all suites |
| `evals_list_runs` | List eval runs (optionally by suite) |
| `evals_get_views` | Return UI view definitions |
| `evals_list_run_results` | List all persisted eval run results, newest first. Returns runs[], count, latest |
| `evals_get_run_result` | Get full details of a run by run_id (case results, scores, reasons, agent info) |

## Evaluators Reference

12 LLMAJ judges across three levels:

| Level | Evaluators |
|-------|-----------|
| OUTPUT_LEVEL | `output` (requires rubric), `helpfulness` |
| TRACE_LEVEL | `faithfulness`, `coherence`, `conciseness`, `harmfulness`, `response_relevance`, `tool_selection`, `tool_parameter` |
| SESSION_LEVEL | `trajectory` (requires rubric), `interactions`, `goal_success` |
