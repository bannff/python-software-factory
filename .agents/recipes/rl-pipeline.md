# Recipe: RL Agent Economy Pipeline

Validates the full loop: sandbox → game → event → blockchain bounty → graph transcript → evals scoring → convergence.

## Bricks Used
- `games` - CTF challenge game engine
- `sandbox` - Docker container execution environment
- `blockchain` - Token economy for agent rewards
- `events` - Event streaming for game lifecycle. `rewards_dispatch` handler triggers RL loop on `graph.completed`
- `evals` - Unified GT scorer (`evals_score_gt` with `match_on` param) + sqlite persistence (`evals_persist_score`)
- `storage` - Durable `eval_results` collection (sqlite via `STORAGE_DOC_BACKEND=sqlite`) — replaces Neo4j edges for longitudinal F1 history
- `graph` - Transcript storage in Neo4j (still used for findings/run topology, not for GT scoring history). Workflows write **`Finding`** rows here (SAST validators, via `idor-validate/SKILL.md` PHASE 3) and **`ProvenExploit`** rows (DAST testers, via `dast-open-scan/SKILL.md` PHASE 4) — see Persistence Contract below (bd:python-factory-evra, bd:python-factory-0s6w).
- `memory` - RL feedback loop: stores scan learnings (TP/FP patterns) for next iteration retrieval
- `metrics` - Convergence tracking via drift detection (replaces bespoke `games_check_convergence`)

## Scenario

An agent plays a CTF challenge in a Docker sandbox. Game outcomes trigger blockchain rewards, graph transcript storage, and evals scoring. Convergence detection decides when to stop iterating.

## Prerequisites

- Docker daemon running (for sandbox Docker adapter)
- AWS credentials (for evals Bedrock scoring — optional, skipped if unavailable)
- `STORAGE_DOC_BACKEND=sqlite` (default — durable doc store at `./.storage/docs.db`, used by `evals_persist_score`)
- Neo4j is **NOT** required for the RL loop. Findings/transcripts can use the in-memory `nx.DiGraph` backend; longitudinal F1 history lives in sqlite, not Neo4j edges.

## Steps

### Step 1: Initialize Games + Sandbox

```python
from factory.games.runtime.runtime import GamesRuntime
from factory.sandbox.runtime.adapters.docker_adapter import DockerAdapter

games = GamesRuntime()
sandbox = DockerAdapter(default_image="alpine:latest")
```

### Step 2: Provision Sandbox Environment

```python
import asyncio

env_id = asyncio.run(sandbox.provision({"image": "alpine:latest"}))
health = sandbox.health_check()
# {"healthy": True, "adapter": "docker", "docker_version": "..."}
```

### Step 3: Create CTF Game

```python
import hashlib

flag = "CTF{test_flag_123}"
flag_hash = hashlib.sha256(flag.encode()).hexdigest()

state = games.create_game(
    game_type="ctf_challenge",
    config={
        "challenge_id": "test-001",
        "description": "Find the flag in /tmp/flag.txt",
        "difficulty": "easy",
        "category": "misc",
        "flag_hash": flag_hash,
        "max_attempts": 10,
        "sandbox_env_id": env_id,
    },
    player_names={1: "test-agent"},
)
game_id = state.game_id
# state.status == "active"
```

### Step 4: Agent Plays — Execute Commands in Sandbox

```python
# Agent explores the sandbox
result = asyncio.run(sandbox.execute(env_id, "ls /tmp"))
# Record the action in the game
move = games.make_move(game_id, 1, {"action": "execute", "command": "ls /tmp"})

# Agent reads a file
result = asyncio.run(sandbox.execute(env_id, "cat /etc/hostname"))
move = games.make_move(game_id, 1, {"action": "read_file", "path": "/etc/hostname"})

# Agent submits wrong flag
move = games.make_move(game_id, 1, {"action": "submit_flag", "flag": "wrong"})
# move.reward == {1: -0.1}, move.terminal == False

# Agent submits correct flag
move = games.make_move(game_id, 1, {"action": "submit_flag", "flag": flag})
# move.reward == {1: 1.0}, move.terminal == True
```

### Step 5: Process Game Finished (Pipeline)

```python
from factory.games.runtime.game_pipeline import process_game_finished

result = process_game_finished({
    "game_id": game_id,
    "game_type": "ctf_challenge",
    "winner": 1,
    "reward": {1: 1.0},
    "move_count": 4,
    "move_history": state.move_history,
    "config": state.config,
    "players": {1: "test-agent"},
})
# result["graph"]["stored"] == True (if Neo4j available)
# result["blockchain"]["claimed"] == True (if blockchain available)
# result["evals"]["scored"] == True (if Bedrock available)
# result["memory"]["stored"] == True (stores TP/FP learnings for RL feedback loop)
#   — content: "Scan learnings [<vuln_class>] run=<id>: N findings, X TP, Y FP..."
#   — tags: [vuln_class, "scan-learnings", run_id]
#   — retrieved by next iteration via memory_retrieve(query="<vuln_class> scan learnings")
```

### Step 6: Convergence Detection (via Metrics Brick)

The bespoke `games_check_convergence` tool was removed. Use `metrics_detect_drift` from the metrics brick instead.

```python
# Via MCP:
# call_brick_tool(brick_name="metrics", tool_name="metrics_detect_drift",
#   arguments='{"metric_id": "pipeline-f1", "baseline_period": "7d", "current_period": "24h", "threshold": 0.1}')

# The rewards_dispatch handler automatically records metrics after each run:
# - pipeline-f1, pipeline-precision, pipeline-recall
# - pipeline-true-positives, pipeline-false-positives, pipeline-false-negatives
# - pipeline-tokens-minted

# Check if F1 has plateaued:
result = metrics_detect_drift(
    metric_id="pipeline-f1",
    baseline_period="7d",  # Compare against last week
    current_period="24h",  # Current performance
    threshold=0.1,         # 10% change threshold
)
# result["drift_detected"] == True means significant change (could be improvement or regression)
# Use metrics_get_trend to see direction
```

### Step 7: Event-Driven RL Loop (Automatic)

The RL loop is now fully event-driven and polymorphic:

1. Hook emits `graph.completed` after ANY security workflow
2. Subscription `auto-rewards-on-workflow-complete` triggers `rewards_dispatch`
3. Handler delegates to existing bricks via MCP:
   - `games_process_workflow_rl` for GT scoring, blockchain rewards, memory learnings
   - `metrics_record` for convergence tracking metrics
   - `metrics_detect_drift` for plateau detection

Inside `process_workflow_rl()` the unified scorer is reached through `evals_evals_score_gt` and the result is then persisted to sqlite via `evals_evals_persist_score`:

```python
# Inside _rl_stages._score (called by process_workflow_rl)
# SAST workflows match on (cwe, file). DAST falls back to the scorer's
# default match_on which covers (cwe, file, method, path).
kwargs: dict[str, Any] = {"findings": findings, "gt_entries": gt_entries}
if workflow_type == "sast":
    kwargs["match_on"] = ["cwe", "file"]
scoring = invoker("evals_evals_score_gt", **kwargs)

# Then in workflow_rl.process_workflow_rl, immediately after `rl.scored`:
# Best-effort sqlite persist via storage brick. Never raises — score
# persistence is observability, not control flow.
invoker(
    "evals_evals_persist_score",
    run_id=run_id,
    workflow_type=workflow_type,   # resolved from "auto" via _detect_type
    target_app=target_app,
    vuln_class=vuln_class,
    scoring=scoring,
)
# Writes one row to the `eval_results` collection with doc_id = f"eval-{run_id}".
# sqlite INSERT OR REPLACE means re-runs MERGE in place.
```

To query longitudinal F1 history (replaces the old Cypher-over-`EVALUATED_AGAINST` pattern):

```python
# Last 10 IDOR runs against WebGoat — sorted newest-first, limited to 10.
result = call_brick_tool(
    brick_name="storage",
    tool_name="storage_doc_query",
    arguments='{"collection": "eval_results", "query": {"vuln_class": "IDOR", "target_app": "WebGoat"}, "limit": 10}',
)
```

#### RL Lifecycle Events

`process_workflow_rl()` emits these games-internal lifecycle events through `event_emitter` (separate from the canonical learning-loop events in `docs/polylith/learning-event-taxonomy.md`). All payloads include the canonical RL context (`workflow_id`, `workflow_run_id`/`run_id`, `vuln_class`, `workflow_type`, `target_app`, `session_id`).

> **Key alias**: `workflow_id` is the canonical key going forward. The legacy `graph_id` key still works — `LearningEventPayload` accepts either via Pydantic `AliasChoices('workflow_id', 'graph_id')` and producers dual-emit both during the deprecation window. New consumers should read `workflow_id`; existing `graph_id` readers keep functioning unchanged.

| Event | Emitted | Extra payload |
|-------|---------|---------------|
| `rl.started` | Entry to `process_workflow_rl()` | — |
| `rl.findings.collected` | After querying graph for findings | `findings_count`, `gt_entries_count` |
| `rl.scored` | After GT scoring via the unified `evals_evals_score_gt` tool | `precision`, `recall`, `f1`, `true_positives`, `false_positives`, `false_negatives` |
| `rl.reward.processed` | After reward planning | `outcome`, `minted`, `amount`, `error_summary` |
| `rl.memory.processed` | After learning-storage planning | `outcome`, `stored`, `error_summary` |
| `rl.completed` | End of pipeline | `findings_count`, `f1` |
| `rl.failed` | On exception | `failed_stage`, `error_summary` |

After `rl.scored`, the pipeline calls `evals_evals_persist_score` to write the P/R/F1 row to the sqlite `eval_results` collection (best-effort, no event — the persist call itself is fire-and-forget). Doc id is `f"eval-{run_id}"`, so re-runs MERGE in place via sqlite `INSERT OR REPLACE` instead of duplicating.

#### Closure Observability — Canonical Learning Events (post-`reward.computed` cascade)

These two canonical learning-loop events close the RL loop on the read side and surface improvement verdicts. Both validate against `LearningEventPayload` (see `components/events/src/factory/events/learning_contracts.py`) and carry `idempotency_key` so re-deliveries are no-ops.

| Event | Fired by | When | Payload (extras beyond canonical RL context) | bd |
|-------|----------|------|----------------------------------------------|-----|
| `learning.applied` | `memory/runtime/learning_emit.py` from `memory_retrieve` | Retrieve returns ≥1 memory tagged `*-learnings` (read-side closure of bd-61yn "No RL loop visibility") | `agent_id`, `retrieved_count`, `retrieved_memory_ids`, `query` (truncated 256 chars). `idempotency_key=learning_applied:{run_id}:{agent_id}:{sha256(query)[:16]}` | bd:python-factory-o7t8 |
| `workflow.improvement` | `events/runtime/learning_handlers/improvement.py` (subscription `auto-improvement-on-reward-computed`, **priority 7** — fires after memory at 8, before convergence at 6) | After `reward.computed`. Reads last N=10 prior runs of same `(workflow_type, target_app, vuln_class)` from sqlite `eval_results`, computes baseline as mean F1 of priors, emits delta + verdict | `baseline_score`, `current_score`, `delta`, `baseline_run_ids`, `verdict` ∈ {`improved` Δ≥+0.05, `regressed` Δ≤−0.05, `stable` \|Δ\|<0.05, `baseline_set` N<3 priors}. Module-level `VERDICT_*` constants in `learning_contracts.py` | bd:python-factory-kq6u |

Why sqlite, not Neo4j edges? Longitudinal GT scoring used to materialize `WorkflowRun -EVALUATED_AGAINST-> GTEntry` edges via a deleted `_rl_gt_edges.py` writer (and a `rl.gt.edges.written` lifecycle event). That path was removed in bd-y9tq because the local dev stack no longer runs Neo4j — `STORAGE_DOC_BACKEND=sqlite` is already the default durable doc store, queries with `storage_doc_query` are an existing tool, and rows are deterministically `INSERT OR REPLACE`-keyed. "F1 over the last 10 runs for IDOR on WebGoat" is now a doc-store query, not a Cypher query.

#### Read-side closure — chat agent recall plugin (bd:python-factory-u3xy)

The two events above surface RL signal at the event bus, but the chat agent gets context from its message stream, not from event subscriptions. `LearningRecallPlugin` (`components/agent/src/factory/agent/plugins/learning_recall.py`, 183 LOC) attaches to the persistent chat `Agent` via `HookProvider` on `BeforeInvocationEvent`. Each turn it extracts the last user message text, calls `memory_retrieve(query=text[:256], user_id="kiro-agent", limit=5, min_relevance=0.3)` through the `tool_invoker` service, filters the response to entries whose `metadata.tags` end in `-learnings` (same suffix predicate `memory/runtime/learning_emit.py` uses on the write side, so the read-side filter matches the `learning.applied` emission contract), and on hit prepends a `Prior runs (recall, system-supplied):` block to the user message in place via `event.messages` mutation — the only field `BeforeInvocationEvent._can_write` whitelists (Strands SDK 1.40, `strands/hooks/events.py:62-64`). The mutation lands in conversation history via `FileSessionManager` (bd-vfgf), so recall persists with the question it grounded and replays cleanly on resume. On miss / failure: silent debug-log no-op (mirrors `collaboration.py`, never raises into the agent loop).

This closes the loop end-to-end. Write side is `games/runtime/workflow_rl.py` persistence (TP/FP scan learnings stored with `*-learnings` tags) plus the bd-o7t8 `learning.applied` event for observability; read side is this plugin pulling those memories back into context every turn so the agent actually USES what prior runs learned. Test invariants P1-P6 pinned in `components/agent/test/factory/agent/test_learning_recall.py`. Feature flag `learning_recall_plugin` in `components/agent/BRICK.yaml`.

#### Persistence Contract — Where `Finding` and `ProvenExploit` Come From

`_collect_findings` reads two graph entity types: `Finding` (SAST runs) and `ProvenExploit` (DAST runs). Those rows don't appear by accident — each workflow has a single, explicit promotion step (bd:python-factory-evra, bd:python-factory-0s6w):

- **SAST + scanner workflows** promote `SuspectedVuln` → `Finding` at the validator/scanner step. The `idor-validate/SKILL.md` PHASE 3 (and the consolidator step in hybrid/swarm paths) writes `entity_type='Finding'` with `entity_id='finding-{run_id}-<n>'` and a `PROMOTED_FROM` edge back to the source `SuspectedVuln`. Same shape applies to `rt-scan-vulns` SCAN_VULNS_SWARM in `defaults_redteam_exploit.py` (bd:python-factory-t754) — writes `entity_type='Finding'` (renamed from `'Vulnerability'`); `events/runtime/dispatch_args.py::_count_findings` reads the `Finding` label so `findings_count` on `learning.metrics.recorded` aggregates uniformly. Single promotion point — consolidators in hybrid/swarm rely on `_mcp_tools` auto-injection (`graph_nodes.py:83`, `swarm.py:158-160`) for `graph_add_entity`; the targeted `defaults_code_scan` keeps writes validator-only by design.
- **DAST + pentest workflows** persist `ProvenExploit` directly at probe-confirmation. The `dast-open-scan/SKILL.md` PHASE 4 writes `entity_type='ProvenExploit'` (renamed from `ConfirmedVuln` in this fix) with a `CONFIRMS` edge from the SAST seed `Finding` and a `CHAINS` edge for attack-chain components. Same shape applies to `redteam-pentest` (PENTEST_IAM_AUDITOR + PENTEST_SECURITY_VALIDATOR in `redteam_playbooks.py`) and the `aws-pentest-ops/SKILL.md` PHASE 4 (bd:python-factory-ksqd) — both persist `entity_type='ProvenExploit'` to graph **before** `memory_store` via the shared `_PERSIST` helper.

Validator-side tool surfaces:
- SAST `_VALIDATOR_TOOLS` (in `defaults_sast_open.py` and `defaults_code_scan.py`): `graph_add_entity`, `graph_add_relationship`, `graph_get_findings_for_run` (plus `think`, `file_read`).
- DAST `_DAST_TOOLS` (in `defaults_dast_open.py`): `graph_add_entity`, `graph_add_relationship`, `graph_find_entities`, `graph_get_findings_for_run`, `memory_store`, `memory_retrieve` (plus `think`, `http_request`, `sandbox_execute`).

Tool names are bare (no `strands_tools.` prefix) per the workflow-tool filter contract at `components/agent/src/factory/agent/executors/_workflow_manager.py:114-124` (canary: `test_sast_task_with_only_strands_tools_filters_out_mcp_tools`, bd:python-factory-42dz). The persistence contract is pinned by 12 property tests in `components/agent/test/factory/agent/test_persistence_contract_properties.py`.

#### Subscription

No bespoke per-workflow logic needed. The subscription in `components/events/src/factory/events/subscriptions/auto-rewards-workflow.yaml` listens for all `graph.completed` events.

```yaml
# Subscription configuration
id: auto-rewards-on-workflow-complete
event_type: "graph.completed"
handler: "mcp:rewards_dispatch"
filters: {}  # No filters — polymorphic handling
```

To manually trigger (e.g., for testing):

```python
# Via MCP (legacy graph_id key — still accepted via the LearningEventPayload alias):
# call_brick_tool(brick_name="events", tool_name="events_publish",
#   arguments='{"event_type": "graph.completed", "payload": {"run_id": "...", "graph_id": "...", "vuln_class": "IDOR"}}')

# Via MCP (canonical workflow_id key — preferred for new code):
# call_brick_tool(brick_name="events", tool_name="events_publish",
#   arguments='{"event_type": "graph.completed", "payload": {"run_id": "...", "workflow_id": "...", "vuln_class": "IDOR"}}')

from factory.events.runtime.runtime import EventsRuntime

events = EventsRuntime()
result = events.publish(
    event_type="graph.completed",
    payload={
        "run_id": "sast-001",
        "graph_id": "rt-sast-scan",  # or "workflow_id": "rt-sast-scan" — both accepted
        "vuln_class": "IDOR",
        "workflow_type": "auto",
        "target_app": "vampi",
    },
    source="manual-trigger",
)
# The rewards_dispatch handler will be invoked automatically
```

### Step 8: Cleanup Sandbox

```python
asyncio.run(sandbox.terminate(env_id))
```

### Step 9: Review Rubrics

```python
from factory.games.runtime.rubrics import list_rubrics, get_rubric

available = list_rubrics()
# ["ctf_challenge", "xss_hunter", "idor_detective",
#  "finding_triage", "task_completion", "connect_four"]

rubric = get_rubric("ctf_challenge")
# Multi-line scoring criteria for OutputEvaluator
```

## Success Criteria

- [x] Docker sandbox provisions and executes commands
- [x] CTF game tracks moves and validates flag submission
- [x] Game pipeline calls graph, blockchain, evals via MCP
- [x] Game pipeline stores learnings in memory (RL feedback loop)
- [x] Convergence detection via metrics brick drift detection
- [x] Security rubrics available for all game types
- [x] Pipeline gracefully skips unavailable bricks
- [x] Event-driven RL loop triggers on graph.completed
- [x] rewards_dispatch delegates to games_process_workflow_rl + metrics tools
- [x] Unified `evals_score_gt` (with `match_on` param) covers SAST and DAST
- [x] `evals_persist_score` writes P/R/F1 to sqlite `eval_results` collection (idempotent doc_id)
- [x] Longitudinal F1 history queryable via `storage_doc_query` (no Neo4j required)
- [x] SAST validator step promotes `SuspectedVuln` → `Finding` with `PROMOTED_FROM` edge (bd:python-factory-evra)
- [x] DAST PHASE 4 persists `ProvenExploit` directly with `CONFIRMS` edge from SAST seed `Finding` (bd:python-factory-0s6w)
- [x] Persistence contract pinned by 12 property tests in `test_persistence_contract_properties.py`

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| games | `factory.games.runtime.runtime.GamesRuntime` | `create_game()`, `make_move()` |
| games | `factory.games.runtime.game_pipeline` | `process_game_finished()` |
| games | `factory.games.runtime.rubrics` | `get_rubric()`, `list_rubrics()` |
| games | `factory.games.runtime.workflow_rl` | `process_workflow_rl()` |
| sandbox | `factory.sandbox.runtime.adapters.docker_adapter` | `DockerAdapter` |
| blockchain | `factory.blockchain.runtime.runtime` | `BlockchainRuntime` |
| evals | via MCP | `evals_evaluate(rubric=...)`, `evals_score_gt(findings, gt_entries, match_on=...)`, `evals_persist_score(run_id, workflow_type, target_app, vuln_class, scoring)` |
| evals | `factory.evals.runtime.gt_scorer` | `score(findings, gt_entries, match_on=("cwe","file","method","path"))` |
| evals | `factory.evals.runtime._persist_score` | `persist_score_result(invoker, run_id, workflow_type, target_app, vuln_class, scoring)` |
| events | `factory.events.runtime.runtime.EventsRuntime` | `publish()` |
| events | `factory.events.runtime.rewards_handler` | `handle_rewards_process()` |
| storage | via MCP | `storage_doc_insert`, `storage_doc_query` (used by evals_persist_score and longitudinal F1 lookups) |
| graph | via MCP | `graph_add_entity`, `graph_add_relationship`, `graph_get_findings_for_run`, `graph_find_entities` (used by SAST validators + DAST testers to write `Finding` / `ProvenExploit` rows; bd:python-factory-evra) |
| metrics | via MCP | `metrics_record()`, `metrics_detect_drift()` |

## MCP Tools

| Tool | Category | Description |
|------|----------|-------------|
| `games_create` | operational | Create game session (accepts optional `config` dict for security games: ground_truth, max_actions, etc.) |
| `games_move` | operational | Make a move |
| `games_ctf_move` | operational | CTF-specific move |
| `games_security_move` | operational | Security game move (analyze_code, trace_dataflow, submit_finding, check_config, test_endpoint, read_file) |
| `games_process_finished` | operational | Trigger post-game pipeline |
| `games_process_workflow_rl` | operational | Per-workflow RL loop: score GT via unified evals scorer, persist to sqlite, mint rewards, store learnings. Auto-detects workflow type from graph_id |
| `sandbox_provision` | operational | Provision Docker container |
| `sandbox_execute` | operational | Run command in container |
| `sandbox_terminate` | operational | Stop and remove container |
| `blockchain_mint` | operational | Mint reward tokens |
| `evals_evaluate` | operational | Score with rubric via Bedrock |
| `evals_score_gt` | deterministic | Unified deterministic P/R/F1 scorer. Optional `match_on` list parameterizes the match key tuple. Default: `("cwe","file","method","path")`. SAST: pass `["cwe","file"]`. Narrow DAST: pass `["cwe","method","path"]` |
| `evals_persist_score` | operational | Persist P/R/F1 row to sqlite `eval_results` collection via `storage_doc_insert`. Idempotent doc_id `eval-{run_id}` (re-runs MERGE in place). Best-effort — returns `{"persisted": False, "reason": ...}` on failure rather than raising |
| `storage_doc_insert` | operational | Insert/upsert document — used internally by `evals_persist_score` |
| `storage_doc_query` | deterministic | Query the `eval_results` collection for longitudinal F1 history |
| `graph_add_entity` | operational | Persist a node (e.g. `Finding`, `ProvenExploit`, `SuspectedVuln`). SAST validators write `Finding` with `entity_id='finding-{run_id}-<n>'`; DAST testers write `ProvenExploit` directly (bd:python-factory-evra, bd:python-factory-0s6w) |
| `graph_add_relationship` | operational | Persist an edge. SAST validators write `PROMOTED_FROM` (Finding → SuspectedVuln). DAST testers write `CONFIRMS` (ProvenExploit → SAST seed Finding) and `CHAINS` for attack-chain components |
| `graph_get_findings_for_run` | deterministic | Run-scoped read used by validators (SAST) and testers (DAST) to fetch existing rows before promotion |
| `graph_find_entities` | deterministic | Used by DAST testers to look up SAST seed `Finding` rows when probing for `ProvenExploit` confirmation |
| `events_publish` | operational | Publish event (triggers rewards_dispatch on graph.completed) |
| `metrics_record` | operational | Record metric data point |
| `metrics_detect_drift` | operational | Detect metric drift for convergence tracking |
