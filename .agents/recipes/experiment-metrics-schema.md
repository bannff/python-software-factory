# Experiment Metrics Schema

Every experiment report (Kiro or Strands) MUST include an `experiment_metrics` section with ALL of these fields. This enables cross-experiment comparison in QuickSight/charts.

## Schema

```json
{
  "experiment_metrics": {
    "meta": {
      "run_id": "string",
      "workflow_type": "kiro|graph|swarm|hybrid",
      "target_app": "string",
      "vuln_class": "string",
      "framework": "string",
      "timestamp": "ISO 8601",
      "pipeline": "recon|sandbox|sast|dast|full",
      "tokens_source": "instrumented|self_reported|unavailable"
    },
    "time": {
      "total_duration_seconds": 0,
      "per_phase_seconds": {"recon": 0, "scanner_a": 0, "scanner_b": 0, "consolidator": 0, "validator": 0, "dast": 0, "post_workflow": 0},
      "time_to_first_finding_seconds": 0,
      "avg_phase_duration_seconds": 0.0
    },
    "scale": {
      "endpoints_discovered": 0,
      "files_scanned": 0,
      "lines_of_code": 0
    },
    "params": {
      "total": 0,
      "user_controlled": 0,
      "subject_derived": 0,
      "system": 0
    },
    "taint": {
      "traces_executed": 0,
      "sink_reached": 0,
      "auth_gap": 0,
      "avg_hop_count": 0.0
    },
    "findings": {
      "raw_before_dedup": 0,
      "after_dedup": 0,
      "confirmed": 0,
      "needs_review": 0,
      "rejected": 0,
      "novel": 0,
      "avg_confidence_score": 0.0,
      "with_taint_trace": 0,
      "with_attack_chain": 0,
      "with_dynamic_proof": 0
    },
    "scoring": {
      "precision": 0.0,
      "recall": 0.0,
      "f1": 0.0,
      "true_positives": 0,
      "false_positives": 0,
      "false_negatives": 0
    },
    "dynamic_verification": {
      "verified_finding": 0,
      "verification_failed": 0,
      "not_tested": 0,
      "sast_predictions_confirmed": 0,
      "sast_predictions_total": 0,
      "sast_correlation_rate": 0.0
    },
    "tokens": {
      "total_tokens": 0,
      "input_tokens": 0,
      "output_tokens": 0,
      "per_agent_tokens": {}
    },
    "tool_calls": {
      "total": 0,
      "per_tool": {},
      "errors": 0
    },
    "agents": {
      "agent_count": 0,
      "models_used": [],
      "cycles_total": 0
    },
    "cost": {
      "estimated_usd": 0.0,
      "per_agent_usd": {},
      "model_pricing_source": "bedrock_on_demand|unavailable"
    },
    "blockchain": {
      "tokens_minted": 0.0,
      "reward_reason": "string"
    },
    "memory": {
      "learnings_stored": 0,
      "learnings_retrieved": 0,
      "kb_queries": 0,
      "graph_queries": 0
    }
  }
}
```

## Notes

- For Kiro workflows: tokens/tool_calls are self-reported by sub-agents (not instrumented). Include `"source": "self_reported"` in those sections.
- For Strands workflows: tokens come from `AgentResult.metrics.accumulated_usage`, tool_calls from `EventLoopMetrics.tool_metrics`. Include `"source": "instrumented"`.
- All numeric fields default to 0 if not available. Never omit a field — charts need consistent schema.
- `scoring` section MUST come from the brick (`games_process_workflow_rl`), never calculated by the orchestrator.
- Prefer `games_write_experiment_report` as the single entry point — it runs RL scoring, batch-records metrics, and writes the JSON report in one call.
