# CAN Failure Prediction — Handover Document

**Date:** 2026-07-28
**Status:** In Progress — Physical failure modes wired, pipeline needs re-run
**Session:** opencode → next agent

---

## 1. Current State

We've built an agentic CAN failure prediction system with context-aware failure injection. The system runs through MCP tools via the control-plane runtime server (port 8000).

### What's Working

| Component | Status | Notes |
|-----------|--------|-------|
| Physical failure modes | ✅ Wired | 8 modes in `_physical_failure_modes.py`, now default dispatch |
| MCP pipeline | ✅ Working | `dataset_submit_generation` → `dataset_get_job` → `dataset_get_artifact` |
| Context-aware injection | ✅ Implemented | adapters for weather, GPS, vehicle metadata |
| Taxonomy extensions | ✅ Complete | 6 new nodes, 5 new relationships |
| Quality checks | ✅ Complete | CAN-specific validation in `quality_can.py` |
| Recipe config | ✅ Updated | Explicit failure_rate=0.1, all 8 modes |

### What Needs Fixing

1. **Failure rate bug** — Pipeline produces ~89% failures instead of configured 10%. The `_AVG_WINDOW=35` heuristic may be miscalculated.
2. **AUROC 0.50** — Models can't learn because of class imbalance (consequence of bug #1).
3. **Re-run needed** — After fixing bug #1, re-run pipeline and retrain models.

---

## 2. Key Files

### Dataset Brick

| File | Purpose |
|------|---------|
| `components/dataset/src/factory/dataset/runtime/adapters/_physical_failure_modes.py` | 8 physical failure modes |
| `components/dataset/src/factory/dataset/runtime/adapters/failure_injection.py` | Orchestrates failure injection |
| `components/dataset/src/factory/dataset/runtime/adapters/_rule_failure_helpers.py` | Mode name constants + re-export |
| `components/dataset/src/factory/dataset/runtime/adapters/_post_injection_verification.py` | Rate verification |
| `components/dataset/src/factory/dataset/runtime/adapters/can_synthesize.py` | SDV synthesis + injection |
| `components/dataset/src/factory/dataset/runtime/adapters/context_ingest.py` | Weather/GPS/vehicle data ingestion |
| `components/dataset/src/factory/dataset/runtime/adapters/context_correlate.py` | Context-failure correlations |
| `components/dataset/src/factory/dataset/runtime/adapters/context_augment.py` | Merge context into CAN records |
| `components/dataset/src/factory/dataset/runtime/recipe.py` | Recipe definitions |
| `components/dataset/src/factory/dataset/runtime/materializer.py` | Job execution + artifact materialization |
| `components/dataset/src/factory/dataset/runtime/quality_can.py` | CAN-specific quality checks |

### ML Brick

| File | Purpose |
|------|---------|
| `components/machine_learning/src/factory/machine_learning/runtime/can_keystone.py` | Pipeline orchestrator |
| `components/machine_learning/src/factory/machine_learning/runtime/can_context_pipeline.py` | Context stage orchestration |
| `components/machine_learning/src/factory/machine_learning/runtime/can_keystone_runner.py` | Stage submit+poll runner |
| `components/machine_learning/src/factory/machine_learning/runtime/adapters/can_inference.py` | Inference with context support |
| `components/machine_learning/src/factory/machine_learning/mcp/can_pipeline_tool.py` | MCP tool surface |

### Graph Brick

| File | Purpose |
|------|---------|
| `components/graph/src/factory/graph/runtime/taxonomies/can_failure_nodes.py` | 14 node types |
| `components/graph/src/factory/graph/runtime/taxonomies/can_failure_relationships.py` | 10 relationship types |

### Steering & Specs

| File | Purpose |
|------|---------|
| `.agents/steering/can-failure-prediction.md` | Main steering doc (includes vision) |
| `.agents/steering/can-handover.md` | This document |
| `.github/spec/can-failure-prediction.md` | Domain spec |
| `.github/spec/can-agentic-orchestration.md` | Agentic architecture spec |

---

## 3. MCP Tools

### Start the control-plane runtime Server

```bash
cd /Users/danielrodrigo/Workspace/python-factory
uv run python projects/the control-plane project/main.py
```

Server runs on `http://localhost:8000`.

### Use MCP Tools

POST to `http://localhost:8000/mcp` with:

```json
{
  "jsonrpc": "2.0",
  "method": "tools/call",
  "params": {
    "name": "call_brick_tool",
    "arguments": {
      "brick_name": "<brick>",
      "tool_name": "<tool>",
      "arguments": "<json_string>"
    }
  }
}
```

### Key Tools

| Brick | Tool | Purpose |
|-------|------|---------|
| dataset | `dataset_submit_generation` | Submit dataset job |
| dataset | `dataset_get_job` | Poll job status |
| dataset | `dataset_get_artifact` | Get output URI |
| machine_learning | `ml_train_timeseries` | Train model |
| machine_learning | `ml_compare_timeseries` | Compare models |
| machine_learning | `ml_list_timeseries_models` | List trained models |

### Example: Run Pipeline

```bash
# Submit job
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_brick_tool","arguments":{"brick_name":"dataset","tool_name":"dataset_submit_generation","arguments":"{...}"}},"id":1}'

# Poll status
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_brick_tool","arguments":{"brick_name":"dataset","tool_name":"dataset_get_job","arguments":"{\"job_id\":\"<id>\"}"}},"id":2}'
```

---

## 4. Data Locations

| Data | Location | Size |
|------|----------|------|
| Decoded CAN | `/Volumes/Crucial X9/can_data/decoded_data/` | 131 GB |
| Per-CAN-ID windows | `/Volumes/Crucial X9/can_data/per_can_id/` | 20,500 samples |
| Fleet tier-3 labels | `/Volumes/Crucial X9/can_data/fleet_tier3/` | 17 MB |
| Decoded CAN signals | `/Volumes/Crucial X9/can_data/fleet_tier2/` | 9.4 GB |
| Dataset store (MCP output) | `.dataset_store/artifacts/` | Varies |
| NPY files for training | `/tmp/25_X.npy`, `/tmp/25_y.npy` | 4.6 MB each |

---

## 5. Beads

| Bead | Status | Task |
|------|--------|------|
| `python-factory-ehn` | ✅ Closed | Physical failure modes |
| `python-factory-2sf` | ✅ Closed | Recipe config |
| `python-factory-ic6` | ✅ Closed | Audit trail |
| `python-factory-b1q` | ✅ Closed | CAN quality checks |
| `python-factory-ctx1` | ✅ Closed | Taxonomy extensions |
| `python-factory-ctx2` | ✅ Closed | context_ingest adapter |
| `python-factory-ctx3` | ✅ Closed | context_correlate adapter |
| `python-factory-ctx4` | ✅ Closed | context_augment adapter |
| `python-factory-ctx5` | ✅ Closed | Pipeline wiring |
| `python-factory-8gy` | ⏳ Open | Dynamic failure injection |
| `python-factory-ctx6` | ⏳ Open | HSML output view |

---

## 6. Immediate Next Steps

### Priority 1: Fix Failure Rate Bug

The pipeline produces ~89% failures instead of 10%. Investigate:

1. Check `_AVG_WINDOW=35` calculation in `failure_injection.py`
2. Verify recipe config propagates correctly through `_parse_config_params`
3. Add debug logging to `inject_failures` to trace the rate calculation
4. Fix and re-run pipeline

### Priority 2: Verify Physical Modes Active

Confirm that `PHYSICAL_RULE_DISPATCH` is being used:
```python
# In failure_injection.py, check line 190
handler = PHYSICAL_RULE_DISPATCH.get(mode)  # Should be this
# NOT
handler = _RULE_DISPATCH.get(mode)  # Legacy
```

### Priority 3: Re-run Pipeline

After fixing bug #1:
```bash
# Submit with correct config
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_brick_tool","arguments":{"brick_name":"dataset","tool_name":"dataset_submit_generation","arguments":"<correct_config>"}},"id":1}'
```

### Priority 4: Train Models

After re-run:
```bash
# Train LightGBM
curl -s -X POST http://localhost:8000/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"call_brick_tool","arguments":{"brick_name":"machine_learning","tool_name":"ml_train_timeseries","arguments":"{\"model_type\":\"lightgbm\",\"X_uri\":\"file:///tmp/25_X_flat.npy\",\"y_uri\":\"file:///tmp/25_y.npy\"}"}},"id":1}'
```

### Priority 5: Get SME Evaluation

After models are trained, consult meta-architect for evaluation.

---

## 7. Design Decisions

| Decision | Rationale |
|----------|-----------|
| Extend dataset brick | Natural extension point for CAN pipeline |
| Context is opt-in | `use_context=False` default preserves backward compat |
| Physical modes are default | `_DEFAULT_MODES = _ALL_MODES` |
| MCP-first | All operations through `call_brick_tool` |
| Models consume context as features | CAN signals + context fields in feature matrix |

---

## 8. Vision

The system should:
1. Inject failures based on **real-world conditions** (weather, driving style, vehicle age)
2. Train models with **CAN signals + context features**
3. Predict failures with **awareness of real-world conditions**
4. Provide **explainable predictions** ("battery failure because temp=-5°C, mileage=142k km")

---

## 9. Key Contacts

- **Meta-architect**: For design reviews and architectural decisions
- **Strands-expert**: For MCP tool patterns and agent orchestration
- **QA tester**: For test verification and quality checks

---

**Document version:** 1.0
**Last updated:** 2026-07-28