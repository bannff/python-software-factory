"""Eval tail agent addenda — session scoring + metrics recording.

Prompt constants for the shared eval tail agent that runs after
each graph workflow. Uses evals_evaluate_session for trajectory
analysis and metrics_record_batch for time-series tracking.
"""
from __future__ import annotations

EVAL_TAIL_PREAMBLE = (
    "You are an evaluation agent. Your job is to score the "
    "completed workflow and record metrics.\n"
    "TARGET APP: {{target_app}}\n"
    "RUN ID: {{run_id}}\n"
    "METRIC PREFIX: {{metric_prefix}}\n\n"
    "KEY BRICKS:\n"
    "- evals: LLMAJ evaluators (trajectory, tool_selection, "
    "tool_parameter, goal_success, helpfulness)\n"
    "- metrics: time-series recording, drift detection, "
    "regression gating (BLOCK/WARN/PASS)\n"
    "- graph: query workflow results by run_id\n"
    "- memory: store eval observations\n\n"
)

EVAL_SESSION_SCORING = (
    "\n== SESSION SCORING ==\n"
    "Score the workflow using LLMAJ evaluators.\n\n"
    "STEP 1 — Gather workflow output via the typed graph tool\n"
    "  (backend-agnostic — no Cypher):\n"
    "  graph_count_entities_by_run(run_id='{{run_id}}',\n"
    "    labels=['SuspectedVuln','Finding','ProvenExploit',\n"
    "            'EndpointInventory','TargetApp'])\n"
    "  Summarize what the workflow produced.\n\n"
    "STEP 2 — Run evaluators:\n"
    "  evals_evaluate_multi(\n"
    "    input_text='{{eval_task_description}}',\n"
    "    output_text=<workflow summary from step 1>,\n"
    "    evaluator_names={{eval_evaluators}},\n"
    "    rubric='{{eval_rubric}}')\n\n"
    "STEP 3 — Store scores in graph:\n"
    "  graph_add_entity(entity_id='eval-{{run_id}}',\n"
    "    entity_type='EvalResult',\n"
    "    properties={run_id, app, scores: <per-evaluator>, "
    "avg_score, pass_rate})\n"
)

EVAL_METRICS_RECORDING = (
    "\n== METRICS RECORDING ==\n"
    "Record workflow metrics for time-series tracking.\n\n"
    "STEP 1 — Record eval scores as metrics:\n"
    "  metrics_record(metric_id='{{metric_prefix}}-trajectory', "
    "value=<trajectory_score>)\n"
    "  metrics_record(metric_id='{{metric_prefix}}-goal-success', "
    "value=<goal_success_score>)\n"
    "  metrics_record(metric_id='{{metric_prefix}}-tool-selection', "
    "value=<tool_selection_score>)\n\n"
    "STEP 2 — Record workflow-specific metrics:\n"
    "  metrics_record(metric_id='{{metric_prefix}}-duration-ms', "
    "value=<total_duration>)\n"
    "  metrics_record(metric_id='{{metric_prefix}}-entity-count', "
    "value=<entities_created>)\n\n"
    "STEP 3 — Store summary in memory:\n"
    "  memory_store(content='EVAL: {{metric_prefix}} run "
    "{{run_id}} — avg_score=<X>, pass_rate=<Y>', "
    "user_id='kiro-agent', category='fact')\n"
)
