"""Shared eval tail swarm — appended to any graph workflow.

Single-agent swarm that scores the workflow output using LLMAJ
evaluators and records metrics. Uses a cheap model (Nova2 Lite)
since it's orchestrating deterministic MCP tool calls.

Context variables (set by parent graph):
  {{run_id}}, {{target_app}}, {{metric_prefix}},
  {{eval_evaluators}}, {{eval_rubric}}, {{eval_task_description}}
"""
from __future__ import annotations

from .models import NOVA2_LITE
from .redteam_eval_addenda import (
    EVAL_TAIL_PREAMBLE,
    EVAL_SESSION_SCORING,
    EVAL_METRICS_RECORDING,
)

RT_EVAL_TAIL_SWARM: dict = {
    "id": "rt-eval-tail",
    "name": "Eval Tail",
    "description": (
        "Scores workflow output with LLMAJ evaluators "
        "(trajectory, tool_selection, goal_success) and "
        "records metrics for time-series tracking."
    ),
    "entry_point": "eval-scorer",
    "max_handoffs": 2, "max_iterations": 10,
    "agents": [
        {"id": "eval-scorer", "model": "",
         "description": "Scores workflow and records metrics.",
         "system_prompt": EVAL_TAIL_PREAMBLE
         + EVAL_SESSION_SCORING + EVAL_METRICS_RECORDING,
         "tools": []},
    ],
}

EVAL_TAIL_SWARMS: list[dict] = [RT_EVAL_TAIL_SWARM]
