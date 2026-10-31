# Kiro SAST Workflow — Full Pipeline Recipe

Kiro orchestrates a SAST code scan by dispatching sub-agents sequentially.
Each sub-agent writes findings to the Neo4j graph via the control-plane runtime power.
Post-workflow pipeline triggers automatically via `games_process_workflow_rl`.

## Context Variables (set before starting)

- `vuln_class`: IDOR, XSS, SQLi, etc.
- `target_app`: e.g. idor_warehouse
- `run_id`: e.g. kiro-sast-warehouse-002
- `sast_workspace`: path to source code

## Phase 1: Scanner A (dataflow focus)

Dispatch `security-engineer` sub-agent with kiro-sast-scanner skill.
Prompt focus: trace data flow from user input to sensitive operations.
Agent writes SuspectedVuln entities to graph with agent_id="kiro-scanner-a".

## Phase 2: Scanner B (authorization focus)

Dispatch `security-engineer` sub-agent with kiro-sast-scanner skill.
Prompt focus: check authorization patterns, missing ownership checks, access control gaps.
Agent writes SuspectedVuln entities to graph with agent_id="kiro-scanner-b".

## Phase 3: Consolidation

Dispatch `security-engineer` sub-agent with kiro-sast-consolidator skill.
Reads SuspectedVuln from graph, groups by (file, function), applies 2/3 voting.
Writes consolidated Finding entities to graph with verdict.

## Phase 4: Validation

Dispatch `security-engineer` sub-agent with kiro-sast-validator skill.
Reads Finding entities from graph, adversarially challenges each one.
Updates verdict in graph: CONFIRMED / NEEDS_REVIEW / REJECTED.

## Phase 5: Post-Workflow Pipeline

Orchestrator triggers the full CompX pipeline:

### 5a. RL Scoring + Blockchain + Memory
```
call_brick_tool(brick_name="games", tool_name="games_process_workflow_rl",
  arguments='{"graph_id": "kiro-sast", "run_id": "{run_id}",
    "vuln_class": "{vuln_class}", "workflow_type": "sast",
    "target_app": "{target_app}"}')
```
This handles: GT scoring (P/R/F1) → blockchain reward → memory learnings.

> Note: `workflow_id` is the new canonical key for learning-loop event payloads (see `LearningEventPayload`); `graph_id` is accepted as a deprecated alias via Pydantic `AliasChoices`. Registry IDs (e.g. `kiro-sast`) are unchanged, so the example above keeps working as-is.

### 5b. LLMAJ Evaluation
```
call_brick_tool(brick_name="evals", tool_name="evals_evaluate_multi",
  arguments='{"input_text": "SAST scan of {target_app} for {vuln_class}",
    "output_text": "<findings summary>",
    "evaluator_names": ["faithfulness", "tool_selection", "goal_success"]}')
```

### 5c. Metrics Recording
```
call_brick_tool(brick_name="metrics", tool_name="metrics_record",
  arguments='{"metric_id": "sast-precision", "value": 0.75,
    "labels": {"workflow": "kiro", "app": "{target_app}", "vuln_class": "{vuln_class}"}}')
```
Record: precision, recall, f1, duration, finding_count.

### 5d. GT Expansion (novel findings)
For findings with no GT match (novel=true):
```
call_brick_tool(brick_name="security", tool_name="security_ingest_gt_entry",
  arguments='{"gt_id": "novel-{run_id}-{n}", "vulnerability_class": "{vuln_class}",
    "cwe": "CWE-639", "service_name": "{target_app}", ...}')
```

## Phase 6: Loop (if improvement detected)

Check convergence using `games_check_convergence`:
```
call_brick_tool(brick_name="games", tool_name="games_check_convergence",
  arguments='{"run_id": "{run_id}", "score": <f1_from_phase_5a>, "patience": 3, "epsilon": 0.01}')
```

The tool uses 2-of-3 voting across:
- **Patience**: Stop after K iterations with no improvement
- **Plateau**: Score hasn't moved > epsilon in recent iterations
- **Regression**: Score dropped significantly from best

If `should_stop=false` AND iteration < 3:
  - Retrieve learnings: `memory_retrieve("IDOR scan learnings")`
  - Re-dispatch scanners with updated context including missed GT entries
  - New run_id: `{base_run_id}-iter-{n}`
Else: STOP and write final report

## Report

Write JSON report to `projects/the control-plane project/challenges/experiments/{run_id}.json`
using the same schema as Strands run reports (see sast-warehouse-005.json).
Set `workflow_type: "kiro"`.
