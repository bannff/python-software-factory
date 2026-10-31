---
inclusion: manual
---
# Unified Graph Taxonomy

> Single source of truth for all node labels, relationship types, and property schemas in the Neo4j knowledge graph.

## Overview

All brick data converges in one Neo4j instance. the control-plane runtime renders it in the Graph view. Two persistence patterns exist:

- **Direct driver** — graph, memory, storage bricks own a `neo4j.GraphDatabase` connection and run Cypher directly.
- **MCP aggregator** — evals, metrics, security, ML bricks call `graph_graph_add_entity` / `graph_graph_add_relationship` through the MCP gateway. Preferred for new adapters.

## Node Labels

### Memory brick (direct driver)

| Label | Props | Notes |
|-------|-------|-------|
| `Memory` | id, user_id, content, memory_type (`short_term`/`long_term`), category, created_at, updated_at, keywords[], context, tags[], evolution_status, embedding[], relevance_score, expires_at, meta_* | A-MEM evolution adds keywords/tags/context |
| `User` | id | Anchor node for `HAS_MEMORY` ownership |

### Graph brick (direct driver)

| Label | Props | Notes |
|-------|-------|-------|
| `__Entity__` | id, type, properties{} | Generic entity (152 existing). Label is the `entity_type` param; `__Entity__` is the base label |
| `Document` | id, content, metadata | Ingested document (576 existing) |

### KB brick

| Label | Props | Notes |
|-------|-------|-------|
| `KBDocument` | id, content, embedding[] | Vector-indexed knowledge base doc (10 existing) |

### Evals brick (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `EvalSuite` | name, description, case_count, created_at | Suite anchor (5 existing) |
| `EvalRun` | suite_id, pass_rate, avg_score, total_cases, failed_cases, run_at, status, config(json), created_at | Completed evaluation run |

### Metrics brick (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `MetricDefinition` | id (`metric-def-{metric_id}`) | Metric registry entry |
| `DataPoint` | metric_id, value, labels(json), timestamp, created_at | Individual recorded value |
| `Snapshot` | metric_id, year, month, created_at | Aggregated metric state |
| `Baseline` | metric_id, tag, values(json), created_at | Named baseline for regression gating |

### Security brick (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `SecurityAction` | action_type, status, created_at, target, summary | Analysis run (threat_model, code_scan, etc.) |
| `Finding` | id, title, description, severity, location, remediation, cwe, evidence, created_at | Security finding (3 existing) |

### Taint Analysis (security brick — planned)

| Label | Props | Notes |
|-------|-------|-------|
| `TaintSource` | id, param, endpoint, file, source_type, created_at | User-controlled entry point (e.g. HTTP param). Created by `security.trace_taint` results persisted to graph |
| `TaintSink` | id, sink_type, function, file, line, created_at | Dangerous operation (e.g. `cursor.execute`, `innerHTML`). Sink patterns come from `vuln_class_config.taint_sinks` |
| `TaintHop` | id, file, function, line, hop_type (controller/service/dao/middleware/unknown), auth_check_present, auth_check_type, code, created_at | Intermediate step in a taint flow. Each hop records whether an auth check was found nearby |

### ML brick (MCP aggregator — NEW)

| Label | Props | Notes |
|-------|-------|-------|
| `FineTuningJob` | id, method, base_model, dataset_ref, status, created_at, completed_at, metrics(json) | Fine-tuning job |
| `Experiment` | id, name, description, tags(json), created_at | ML experiment container |
| `Run` | id, experiment_id, name, status, started_at, ended_at, params(json), metrics(json) | Experiment run |
| `Checkpoint` | id, job_id, step, metrics(json), path, created_at | Training checkpoint |

### Games brick (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `GameSession` | game_type, winner, move_count, reward(json), config(json) | One node per completed game. Created by `game_pipeline._store_transcript` |
| `GameMove` | step, action, command, path, flag, ts, + any extra move dict fields | Individual move within a game. Properties spread from the move dict |

### Telemetry materialization projection (Telemetry brick via MCP)

`run_id` is the durable execution join; `workflow_run_id` is accepted only as a legacy ingress alias and normalized at the boundary. `trace_id`/`span_id` preserve W3C topology and never substitute for `run_id`; session, agent, workflow, graph, and swarm identifiers retain their separate meanings. Telemetry owns authenticated OTLP ingress, normalized/raw evidence, and allowlisted bounded materialization through typed MCP tools. The legacy gateway `graph_sink` is compatibility-only.

A materialized relationship derives its ID from source system, stable source identity/digest, relationship type, and endpoints. Equal replays create-or-match; mismatches are explicit conflicts; rebuild/reconciliation converges from durable references. Graph retains reference/digest and browse metadata—not raw telemetry—and a NetworkX adapter is durable only with explicit persistent restore and reconciliation.

| Label | Props | Notes |
|-------|-------|-------|
| `WorkflowRun` | run_id, status (`running`/`completed`/`failed`), started_at, principal_id (optional), created_at | Root anchor for a workflow execution. ID `workflow-run-{run_id}`. Workflow owns status; Telemetry only projects a bounded reference. |
| `ToolInvocation` | id, brick_name, tool_name, success, latency_ms, error, session_id, principal_id, run_id, sequence (int, run-scoped monotonic), invocation_type, caller, args_summary(json), result_summary(json), created_at | Selected bounded invocation summary, materialized by Telemetry through Graph MCP. `run_id` is canonical; `workflow_run_id` is compatibility-only. |
| `Brick` | name, created_at | Observed brick identity, linked via `INVOKED_ON`. |
| `Session` | id, session_type, principal_id, agent_id, status, started_at, ended_at, metadata(json), created_at | Groups related interaction activity; it does not replace `run_id`. |
| `Swarm` | swarm_id (config id), run_id, entry_point, agent_count, status (`running`/`completed`), started_at, completed_at, execution_time, created_at | Orchestrator node, one per swarm execution. Materialised by `components/events/runtime/lineage_handlers/swarm_lineage.py` on `swarm.launched` / `swarm.completed` events. ID `swarm-{swarm_id}-{run_id}` |
| `Graph` | graph_id (config id), run_id, node_count, entry_points (comma-joined), status (`running`/`completed`/`failed`), started_at, completed_at, failed_at, execution_time, execution_order (comma-joined), error (if failed), created_at | Orchestrator node, one per graph workflow execution. Materialised by `lineage_handlers/graph_lineage.py` on `graph.launched` / `graph.completed` / `graph.failed` events. ID `graph-{graph_id}-{run_id}` |
| `Agent` | agent_id, created_at | See "Other existing" below — also materialised by `lineage_handlers/swarm_lineage.py` on `swarm.node_start` events. ID `agent-{agent_id}` |
| `EvalResult` | run_id, graph_id, workflow_run_id, avg_score (float, 0-1), pass_rate (float, 0-1), evaluators (list[str], JSON-serialized), scores (list[float], JSON-serialized), source (always `auto-eval-dispatch`), created_at | Auto-eval result anchored to its WorkflowRun via `SCORED_BY`. Materialised by `components/events/runtime/dispatch_args.py::_persist_eval_result` whenever an auto-eval completes. ID `eval-auto-{run_id}` |

### Blockchain brick (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `Block` | id, hash, prev_hash, timestamp, merkle_root, tx_count, created_at | Hash-chained block |
| `Transaction` | id, hash, tx_type, amount, memo, nonce, status, created_at | Ledger transaction |
| `Wallet` | id, owner_id, balance, created_at | Agent wallet |
| `Bounty` | id, description, amount, status, criteria(json), created_at | Posted bounty with escrow |

### IDOR Pipeline (security brick + games brick)

| Label | Props | Notes |
|-------|-------|-------|
| `GTEntry` | gt_id, vulnerability_class, cwe, confidence, service_name, fix_commit, fix_cr, created_at | Ground truth vulnerability entry. Seeded via `security_ingest_gt_entry` |
| `AppEndpoint` | endpoint, method, service_name, created_at | HTTP endpoint from GT runtime_evidence. Linked to GTEntry |
| `CodeLocation` | file, function, line_start, line_end, description, created_at | Code location from GT code_evidence. Linked to GTEntry |
| `Commit` | hash, cr_id, description, created_at | Fix commit from GT fix_evidence. Linked to GTEntry |

### CWE Taxonomy (shared reference data)

| Label | Props | Notes |
|-------|-------|-------|
| `CWECategory` | cwe_id, name, description, parent_cwe (nullable), created_at | OWASP/CWE reference node. Seeded via `security_seed_cwe_taxonomy` |

### OCSF Event Schema (shared reference data)

| Label | Props | Notes |
|-------|-------|-------|
| `OCSFEventClass` | class_uid (int), class_name, category_uid (int), category_name, description, created_at | OCSF v1.3 event class. Seeded via `security_seed_ocsf_taxonomy` |
| `OCSFCategory` | category_uid (int), category_name, description, created_at | OCSF v1.3 top-level category (7 total) |

### Kiro Workflow Pipeline (MCP aggregator)

| Label | Props | Notes |
|-------|-------|-------|
| `TargetApp` | id, name, app, tech_stack, framework, security_level, auth_mechanism, ports, endpoints_total, attack_surface_summary, threat_categories, last_recon_run_id, run_id, created_at, updated_at | Written by recon agents. Singleton per app (MERGE semantics) |
| `SuspectedVuln` | id, run_id, app, vuln_class, agent_id, cwe, confidence, confidence_level, file, function, line_start, line_end, code_snippet, reasoning, attack_chain, recommended_test, taint_trace(json), sink, endpoint(json), dynamic_verification_status, created_at | Written by SAST scanner agents |
| `ProvenExploit` | id, run_id, app, vuln_class, cwe, severity, method, path, command_run/http_request, actual_status/http_status, actual_output/response_body, expected_secure, server_feedback, attack_chain, sast_correlation(json), created_at | Written by DAST tester agents |
| `EndpointInventory` | id, run_id, app, endpoints(json[]), count, created_at | Written by SAST scanners. One inventory node per run |
| `ReconSummary` | id, run_id, app, resource_counts(json), confirmed_count, unconfirmed_count, created_at | Written by recon summary agents |
| `ServiceMockConfig` | id, run_id, app, authorizer(bool), credential_store(bool), oauth_provider(bool), rpc_service(bool), credential_file(bool), created_at | Written by recon agents for sandbox setup |

### Other existing (from Neo4j audit)

| Label | Count | Notes |
|-------|-------|-------|
| `Event` | 13 | System/agent events |
| `SwarmRun` | 2 | Multi-agent execution records |
| `AWSResource` variants | — | External topology graph nodes |

## Relationship Types

### Memory brick (direct driver)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `HAS_MEMORY` | User → Memory | — | Ownership |
| `FOLLOWED_BY` | Memory → Memory | — | Temporal sequence (auto-linked on store) |
| `RELATED_TO` | Memory → Memory | — | A-MEM evolution semantic link |
| `EVOLVED_FROM` | Memory → Memory | — | A-MEM audit trail |
| `REFERENCES` | Memory → KBDocument | created_at, score, reason | Cross-domain (evolution-discovered) |
| `MENTIONS` | Memory → Finding | created_at, score, reason | Cross-domain (evolution-discovered) |

### Evals brick (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `EVALUATED_BY` | EvalSuite → EvalRun | — | Suite-to-run link |

### Metrics brick (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `RECORDED_FOR` | DataPoint → MetricDefinition | — | Value-to-metric link |
| `SNAPSHOT_OF` | Snapshot → MetricDefinition | — | Aggregation-to-metric link |
| `BASELINE_OF` | Baseline → MetricDefinition | — | Baseline-to-metric link |
| `COMPARED_TO` | Snapshot → Baseline | signal, delta_pct, threshold_block, threshold_warn, compared_at | Regression comparison result |

### Security brick (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `DISCOVERED` | SecurityAction → Finding | — | Action-to-finding link |
| `CLASSIFIED_AS` | Finding → CWECategory | created_at | CWE classification |
| `CLASSIFIED_AS` | SecurityAction → CWECategory | created_at | CWE classification |
| `CHILD_OF` | CWECategory → CWECategory | — | CWE hierarchy (child → parent) |
| `CONFORMS_TO` | SecurityAction → OCSFEventClass | created_at | OCSF event class conformance |
| `CONFORMS_TO` | Finding → OCSFEventClass | created_at | OCSF event class conformance |
| `BELONGS_TO` | OCSFEventClass → OCSFCategory | — | OCSF class-to-category hierarchy |

### Taint Analysis (security brick — planned)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `FLOWS_TO` | TaintHop → TaintHop | ordinal (int) | Ordered taint propagation between hops |
| `FLOWS_TO` | TaintSource → TaintHop | ordinal (int) | Source to first hop |
| `FLOWS_TO` | TaintHop → TaintSink | ordinal (int) | Last hop to sink (only when `sink_reached=true`) |
| `HAS_TAINT_TRACE` | Finding → TaintSource | hop_count (int), sink_reached (bool), auth_gap (bool), created_at | Links a finding to its taint trace origin. Consolidator and validator query this to ground LLM reasoning in deterministic evidence |

### ML brick (MCP aggregator — NEW)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `TRAINED_BY` | Experiment → FineTuningJob | — | Experiment-to-job link |
| `HAS_RUN` | Experiment → Run | — | Experiment-to-run link |
| `CHECKPOINT_OF` | Checkpoint → FineTuningJob | — | Checkpoint-to-job link |

### Games brick (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `HAS_MOVE` | GameSession → GameMove | — | Session-to-move link (one per move, ordered by `step`) |

### Security brick — IDOR Pipeline additions (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `HAS_ENDPOINT` | GTEntry → AppEndpoint | — | GT entry to its vulnerable endpoint |
| `HAS_CODE_LOCATION` | GTEntry → CodeLocation | — | GT entry to its vulnerable code location |
| `FIXED_BY` | GTEntry → Commit | — | GT entry to its fix commit |
| `EVALUATED_AGAINST` | WorkflowRun → GTEntry | score, verdict (TP/FN), created_at | **DEPRECATED (bd-y9tq, 2026-05-22).** No code currently materializes this edge — the deterministic writer (`games/runtime/_rl_gt_edges.py`) and the `rl.gt.edges.written` lifecycle event were deleted because the local dev stack no longer runs Neo4j. Longitudinal GT scoring history now lives in the sqlite `eval_results` collection (one doc per run, doc_id `eval-{run_id}`), written by the `evals_persist_score` MCP tool and queryable via `storage_doc_query`. The schema row is preserved for historical reads — older Neo4j databases may still contain these edges from runs prior to the cutover. New code MUST NOT write `EVALUATED_AGAINST`. The `graph` brick's IDOR taxonomy doc (`docs_taxonomy_idor.py`) still lists this type as reference data only. |

### Blockchain brick (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `PREV_BLOCK` | Block → Block | — | Hash chain link |
| `CONTAINS_TX` | Block → Transaction | — | Block-to-tx |
| `SENT` | Wallet → Transaction | — | Sender |
| `RECEIVED` | Transaction → Wallet | — | Receiver |
| `POSTED_BOUNTY` | Wallet → Bounty | — | Bounty poster |
| `CLAIMED_BOUNTY` | Wallet → Bounty | claimed_at | Bounty claimer |
| `FUNDED_BY` | Bounty → Transaction | — | Escrow tx |

### Telemetry materialization projection (Telemetry brick via MCP)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `INVOKED_ON` | ToolInvocation → Brick | — | Selected bounded invocation-to-brick link. |
| `FOLLOWED_BY` | ToolInvocation → ToolInvocation | — | Session-scoped temporal sequence when materialized. |
| `NEXT_IN_RUN` | ToolInvocation → ToolInvocation | run_id, sequence (int) | Run-scoped chain; `run_id` is canonical. |
| `CONTAINS_INVOCATION` | Session → ToolInvocation | ordinal (int) | Ordered call within a session. |
| `EXECUTED_BY` | Session → Agent; WorkflowRun → Swarm \| Graph | — | Endpoint labels distinguish interaction actor from native execution topology. |
| `INITIATED_BY` | Session \| WorkflowRun → User | — | Principal that initiated the interaction/run. |
| `CONTAINS_SESSION` | WorkflowRun → Session | — | A run may span sessions; session is supporting context. |
| `CONTAINS` | Swarm \| Graph → Agent | — | Participating agents when a bounded execution summary is materialized. |
| `HANDED_OFF_TO` | Agent → Agent | run_id, ordinal (int) | Selected swarm handoff evidence; not a Workflow scheduling control input. |
| `SCORED_BY` | WorkflowRun → EvalResult | avg_score, pass_rate | Durable Eval reference attached through the normal run correlation. |
| `FULFILLS` | Session → Bounty | — | Links bounty-driven sessions to their bounty. |
| `PRODUCED` | Session → EvalRun | — | Links sessions that trigger evals. |

### Kiro Workflow Pipeline (MCP aggregator)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `RECON_OF` | ReconRun → TargetApp | run_id, created_at | Links a recon run to the target app it profiled |

### Graph brick (generic)

| Type | Direction | Props | Notes |
|------|-----------|-------|-------|
| `RELATED_TO` | __Entity__ → __Entity__ | id, + custom | Generic relationship |

## Entity ID Conventions

Kebab-case with brick prefix. UUIDs where noted.

| Label | Pattern | Example |
|-------|---------|---------|
| Memory | UUID | `mem-abc123` |
| EvalSuite | `eval-suite-{suite_id}` | `eval-suite-security-v2` |
| EvalRun | `eval-run-{run_id}` | `eval-run-7f3a` |
| EvalResult | `eval-auto-{run_id}` | `eval-auto-run-xyz` |
| MetricDefinition | `metric-def-{metric_id}` | `metric-def-coverage` |
| DataPoint | `dp-{metric_id}-{timestamp}` | `dp-coverage-1709856000.0` |
| Snapshot | `snap-{metric_id}-{year}-{month}` | `snap-coverage-2026-3` |
| Baseline | `baseline-{metric_id}-{tag}` | `baseline-f1-v1.0` |
| SecurityAction | `action-{analysis_id}` | `action-scan-001` |
| Finding | `finding-{finding_id}` | `finding-scan-001-0` |
| CWECategory | `cwe-{numeric_id}` | `cwe-79` |
| OCSFEventClass | `ocsf-class-{class_uid}` | `ocsf-class-2001` |
| OCSFCategory | `ocsf-cat-{category_uid}` | `ocsf-cat-5` |
| FineTuningJob | `ft-job-{job_id}` | `ft-job-llama-v3` |
| Experiment | `ml-exp-{experiment_id}` | `ml-exp-rag-tuning` |
| Run | `ml-run-{run_id}` | `ml-run-42` |
| Checkpoint | `ml-ckpt-{checkpoint_id}` | `ml-ckpt-step-500` |
| `ToolInvocation` | `tool-inv-{stable_source_id}` | `tool-inv-trace-span-or-event` | Telemetry materialization uses a stable source event/span identity when available; legacy gateway-generated UUIDs remain compatibility data. |
| Session | `session-{session_id}` | `session-bounty-3696122e92c9` |
| WorkflowRun | `workflow-run-{run_id}` | `workflow-run-rt-sast-scan-42` |
| Swarm | `swarm-{swarm_id}-{run_id}` | `swarm-pentest-assessment-run-xyz` |
| Graph | `graph-{graph_id}-{run_id}` | `graph-redteam-pipeline-run-g1` |
| Brick | `brick-{brick_name}` | `brick-events` |
| GameSession | `game-{game_id}` | `game-tictactoe-7f3a` |
| GameMove | `move-{game_id}-{step}` | `move-tictactoe-7f3a-0` |
| GTEntry | `gt-{gt_id}` | `gt-IDOR-SSAMS-001` |
| AppEndpoint | `endpoint-{service}-{method}-{path_hash[:8]}` | `endpoint-ssams-DELETE-a1b2c3d4` |
| CodeLocation | `codeloc-{file_hash[:8]}-{line_start}` | `codeloc-a1b2c3d4-30` |
| Commit | `commit-{hash[:12]}` | `commit-37c96eeae5a7` |
| Block | `block-{height}` | `block-42` |
| TaintSource | `taint-src-{endpoint_hash[:8]}-{param}` | `taint-src-a1b2c3d4-userId` |
| TaintSink | `taint-sink-{file_hash[:8]}-{line}` | `taint-sink-e5f6a7b8-142` |
| TaintHop | `taint-hop-{file_hash[:8]}-{line}` | `taint-hop-c9d0e1f2-87` |
| Transaction | `tx-{hash[:12]}` | `tx-a1b2c3d4e5f6` |
| Wallet | `wallet-{owner_id}` | `wallet-agent-001` |
| Bounty | `bounty-{uuid[:12]}` | `bounty-f7e8d9c0b1a2` |
| TargetApp | `app-{target_app}` | `app-my-service` |
| SuspectedVuln | `suspected-vuln-{run_id}-{n}` | `suspected-vuln-r42-0` |
| ProvenExploit | `exploit-{run_id}-{n}` | `exploit-r42-0` |
| EndpointInventory | `endpoint-inventory-{run_id}` | `endpoint-inventory-r42` |
| ReconSummary | `recon-summary-{run_id}` | `recon-summary-r42` |
| ServiceMockConfig | `svc-mock-{run_id}` | `svc-mock-r42` |

## Workflow-id Naming Convention (open vs targeted)

Registry ids encode whether a registration is `kind=workflow` or
`kind=graph`, and (for security workflows) whether the variant is
class-targeted or class-open:

- **`kind=workflow`** registrations drop the `rt-` prefix when newly
  authored: `recon-app`, `sandbox-setup`, `sast`, `dast`. The
  in-place SAST canary kept its original id `rt-sast-scan` for
  consumer back-compat (bd-a4h7).
- **`kind=graph`** registrations keep the `rt-` prefix:
  `rt-recon-graph`, `rt-recon-hybrid`, `rt-sast-scan-hybrid`,
  `rt-scan-idor`, `rt-scan-idor-hybrid`.
- **Targeted variants** keep `vuln_class` in `context_vars` for
  GT-eval comparison runs (one class per invocation).
- **Open variants** drop `vuln_class` and let the agent chain
  attacks across all 9 classes (IDOR / SQLi / XSS / SSRF / CSRF /
  Path-Traversal / Cmd-Injection / Deserialization / Mass-Assignment).
- **Hybrids stay `kind=graph`** because Strands `WorkflowManager`
  cannot embed a Swarm — they're azca experiment arms with
  model-diversity ensembles, dispatched via `GraphExecutor` +
  `SwarmNode`. See `.agents/recipes/workflow-migration.md`.

## Property Conventions

- **`created_at`** — required on all nodes. ISO 8601 UTC string.
- **Complex values** — JSON-serialized strings (Neo4j doesn't support nested maps). Props: `config`, `labels`, `params`, `metrics`, `tags`.
- **Timestamps** — ISO 8601 for dates (`created_at`, `run_at`). Unix epoch float for time-series (`DataPoint.timestamp`).
- **Arrays** — `keywords[]`, `tags[]`, `embedding[]` stored as Neo4j native lists.
- **Cross-domain edge props** — `score` (float), `reason` (string), `created_at` (ISO 8601).

## MCP Aggregator Pattern

New adapters should use the MCP aggregator instead of direct Neo4j drivers. The evals `graph_adapter.py` is the canonical exemplar.

```python
# Lazy-load the aggregator (avoids import-time coupling)
def _get_aggregator() -> Any:
    from factory.mcp_server.interface import get_server, get_aggregator
    get_server()
    return get_aggregator()

def _invoke(tool_name: str, **kwargs: Any) -> Any:
    agg = _get_aggregator()
    if agg is None:
        raise RuntimeError("MCP aggregator not available")
    return agg.invoke_tool(tool_name, **kwargs)

# Create a node
_invoke("graph_graph_add_entity",
    entity_id="eval-run-42",
    entity_type="EvalRun",
    properties={"suite_id": "s1", "pass_rate": 0.95, "created_at": _utcnow()})

# Create a relationship
_invoke("graph_graph_add_relationship",
    relationship_id="evaluated-by-42",
    relationship_type="EVALUATED_BY",
    source_id="eval-suite-s1",
    target_id="eval-run-42")

# Find entities using the portable typed API
_invoke("graph_graph_find_entities", entity_type="EvalRun",
        properties={"suite_id": "s1"}, limit=100)
```

## Domain Pack Registry (taxonomy extensions)

Domain packs live in `components/graph/src/factory/graph/runtime/taxonomies/` — pure data
(node types / relationship types / conventions) plus a `register()` call against the
append-only `taxonomy_registry` (`register_extension` raises on collision; same-domain
re-registration is always an error). Resolve a merged view with
`resolve_domain_taxonomy(<domain>)`; the security domain always seeds the base.

| Domain | Files | Public API |
|--------|-------|-----------|
| `can_failure` | `can_failure.py`, `can_failure_nodes.py`, `can_failure_relationships.py` | `factory.graph.interface.register_can_failure_taxonomy` |
| `edge` | `edge.py`, `edge_nodes.py`, `edge_relationships.py` | `factory.graph.interface.register_edge_taxonomy` |

### `edge` — mesh workflow coordination

Vocabulary of the mesh-workflow design
(`projects/the control-plane project/experiments/edge_models/edge-mesh-workflow-design/`): the registry is
the source of truth for exact property lists and sha256 id derivations; this section indexes it.

- **Nodes:** `EdgeDevice` (mesh member, `mesh_membership`), `EdgeWorkflow` (workflow
  instance + payload↔registry version contract), `EdgeClaim` (coexisting content-addressed
  leases, winner = lowest `claimant_device_id` among unexpired), `EdgeResult` (append-only
  execution evidence + outbox intent docs), `EdgeTransition` (signed journal entry in a
  content-addressed transitions map), `EdgeObservation` (sensor/model trigger fact).
- **Relationships:** `EDGE_OBSERVED_ON`, `EDGE_TARGETS`, `EDGE_TRIGGERED_BY`,
  `EDGE_CLAIMED_BY`, `EDGE_PRODUCED`, `EDGE_JOURNALED`, `EDGE_VERIFY_FOR` (C7
  check-before-act predicate).
- **Id conventions:** content-addressed per design.md §2 / edge-cases.md §C1 — e.g.
  `wf_<sha256(target_device + action + blueprint_version + trigger_id)[:24]>`,
  `claim-<sha256(workflow_id + claimant_device_id)>`; same-id/different-content is an
  integrity error, never silent LWW.
- **Epistemic status:** optional property convention on every node —
  `harness-proven` | `sdk-live` | `convention` | `q1-gap`.
- Auto-registered on MCP server surface alongside `can_failure`; exposed at
  `graph://schemas/taxonomy/edge`.

## Naming Rules

| Element | Convention | Examples |
|---------|-----------|----------|
| Node labels | PascalCase | `FineTuningJob`, `EvalRun`, `KBDocument` |
| Relationship types | SCREAMING_SNAKE_CASE | `RECORDED_FOR`, `EVALUATED_BY`, `CHECKPOINT_OF` |
| Entity IDs | kebab-case with brick prefix | `eval-run-`, `ft-job-`, `ml-exp-`, `cwe-` |
| Properties | snake_case | `created_at`, `pass_rate`, `base_model` |

## Known caveat: edge collision on nx.DiGraph backend

On the in-memory `nx.DiGraph` backend, edges dedupe by `(source, target)`. Within a single session, `NEXT_IN_RUN` and `FOLLOWED_BY` share endpoints — `FOLLOWED_BY` wins because it is written second and overwrites the earlier `NEXT_IN_RUN` entry. For visualizations and run-topology queries, treat the `sequence` property on `ToolInvocation` as canonical instead of querying raw `NEXT_IN_RUN` edges; that is what `graph_get_run_topology` does. A future Neo4j backend (which keys edges by type as well as endpoints) would have no collision.
