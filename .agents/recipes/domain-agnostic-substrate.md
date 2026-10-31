# Recipe: Domain-Agnostic Substrate

End-to-end walkthrough for adding a new domain agent (wine, workout, anything non-security) on top of the the control-plane runtime substrate. Adding a persona is a register-and-config exercise — no engine code change. Two epics built this substrate. **`python-factory-hadbi`** made the chat persona, graph typed-reads, games RL loop, and memory recall domain-agnostic — `domain_class` / `count_labels` / `taxonomy_edges` threaded through the MCP boundary, the events `LearningEventPayload`, cross-brick correlation, and per-node skills; P3 burndown then added the graph taxonomy registry + `graph://schemas/taxonomy/{domain}` resource and the `memory_retrieve` `tags`/`metadata` filters; wave-3 `ziwqs` made `agent.agent_id` the per-agent recall namespace, retracting the short-lived `AgentConfig.domain_class` field. **`python-factory-d4roe` (this branch)** makes persona authoring a runtime operation and adds per-thread persona selection — see the d4roe note below. **`python-factory-czpw` (this branch, uncommitted)** makes the chat agent manage a team of sub-agents conversationally — CREATE (`agent_create_agent`, now chat-callable) / SPAWN (`spawn_subagent`) / DELETE (`agent_delete_agent`) / SKILLS (`agent_list_skills`); see Step 1c. Per-bd landing detail lives in the Phase landings table at the foot of this recipe; security defaults remain byte-identical throughout.

> **Epic `python-factory-d4roe` — runtime authoring + per-thread persona.** Personas now have TWO sources behind ONE read path. Built-ins stay in CODE (`AGENTS_TYPED`); user personas are DATA behind a `RegistryStore` port (`DiskRegistryStore` locally; an AgentCore-backed adapter slots in later behind the same Protocol). `registry/unified.py::unified_personas` is the single read path — built-ins seeded first, store overlaid, built-ins WIN on id collision. The `agent_create_agent` `@authoring` tool (Step 1b) writes a persona and reloads the registry so it resolves for chat AND discovery with NO restart. The `/` persona palette (Step 4b) selects a persona per-thread via `RunAgentInput.forwardedProps.companion_x_agent_id`. `AgentConfig.id` is charset-locked `^[a-z0-9][a-z0-9_-]{0,127}$` — REJECT not coerce (bd:python-factory-67qvz: closes a case-fold data-loss between the disk/in-memory stores on case-insensitive filesystems AND a `FileSessionManager` session-id path-traversal vector).

> **Source of truth.** `.agents/steering/brick-inventory.md` and `.agents/steering/mcp-tools.md` carry the canonical surface descriptions. This recipe is the integration playbook.

## Bricks Used

- `agent` — chat-persona registry, unified persona read path (`registry/unified.py::unified_personas`), `AgentConfig(id, name, system_prompt, model, tools, skills, description)`. `id` charset-locked `^[a-z0-9][a-z0-9_-]{0,127}$` (REJECT not coerce, bd:67qvz). Per-agent recall via `agent.agent_id` = Strands native (bd:ziwqs). Native spawn tools: `spawn_subagent` (single agent), `spawn_swarm` (Swarm, free collab), `spawn_graph` (Graph, directed pipeline). `AgentSkills` via `plugins=` at ctor time — NOT `add_hook()`.
- `graph` — typed reads with `taxonomy_edges` (bd:ecph9 + le9gu); `get_findings_for_run` / `get_recent_findings` / `get_workflow_summary`. Per-domain taxonomy registry (`runtime/taxonomy_registry.py`) + `graph://schemas/taxonomy/{domain}` resource template (bd:qm07q).
- `games` — RL pipeline reads `domain_class` + per-call `count_labels` / `taxonomy_edges` through `games_process_workflow_rl` and `games_write_experiment_report` (bd:qer1z + twxj0 + tmlrx). Memory tags dual-emit so security + per-domain recall both work.
- `events` — `LearningEventPayload.domain_class` field with `AliasChoices("domain_class","vuln_class")` (bd:twxj0).
- `evals` — `evals_persist_score` accepts `domain_class` (bd:tmlrx).
- `mcp_utils` — `correlation._CANONICAL_KEYS` includes `domain_class` (bd:sm1va).
- `memory` — `memory_retrieve` accepts `tags:list[str]|None` (bd:lin6p) and `metadata:dict[str,str]|None` (bd:b2d2o). Tier-1 native push-down on neo4j + neo4j_embedding. Cypher injection guard at Pydantic + adapter boundaries (`re.fullmatch`). Per-domain RL recall closed end-to-end (bd:ziwqs + vs1vu).

## Prerequisites

- the control-plane runtime API on `http://localhost:8001`, Next dashboard on `http://localhost:3000`. `COMPANION_X_CHAT_MODEL` set to any chat-capable model.
- Optional: `skills/<your-skill>/SKILL.md` for extra workflow context via Strands `AgentSkills`. No AWS, Docker, or Neo4j required (memory adapters carry the load).

## Design verdicts (key references)

- meta-architect: `9a4aba3c` (agent IS the domain); `87327b75` (trinary None/[]/list contract); `2efd2a40` (taxonomy registry + memory post-filter); `f279063c` (metadata asymmetric default + re.fullmatch injection guard); `afdb867a` (ziwqs — drop domain_class, agent_id is the namespace); `9d6a73fb` + `56b267c3` + `a19ef414` (d4roe unification, id charset, chat boundary).
- strands-expert: `9b6d46cd` (LOUD-FAIL on env miss); `1c5df3c7` (build_skills_plugin in neutral adapter); `68ea2c63` (agent_id canonical recall primitive); `6e22d1bb` (per-thread persona via forwardedProps); `209fb838` + `cc6b9e58` (spawn_subagent native @tool; spawn_swarm Swarm SESSIONLESS, G2 translator); `0bf122e1` (spawn_graph GraphBuilder API, stream_async yields same multiagent_node_* shapes).
- qa-tester: `1e7ce24b` (substrate prep) + `96d9e8ac` (P3 wave 1) + `8862f537` (re.fullmatch fix) + `3c837989` (ziwqs APPROVE).

## Steps

### Step 1: Register your agent (static, code path)

Create `components/agent/src/factory/agent/registry/defaults_<your_domain>.py`. Append the `AgentConfig` to `AGENTS_TYPED` in `defaults.py`. Requires a process restart. For on-the-fly personas, see Step 1b.

```python
WINE_PAIRING_AGENT = AgentConfig(
    id="wine-pairing", name="Wine Pairing Sommelier", model=SONNET,
    system_prompt="You are a sommelier...",
    skills=["wine-pairing"],   # gates AgentSkills via plugins= at Agent ctor time
)
# defaults.py: CHAT_AGENTS = [COMPANION_X_DEFAULT_AGENT, WINE_PAIRING_AGENT]
```

`cfg.id` IS the recall namespace (bd:ziwqs). No `domain_class` field — register with a unique `id` and per-agent recall lights up automatically.

### Step 1b: Author a persona at runtime (no restart)

bd:python-factory-d4roe.2. Call `agent_create_agent` instead of editing code — thin facade over `write_yaml_config("agent", config)` + `agent_registry.load()`, persisted to `DiskRegistryStore`, immediately resolvable with NO restart.

```python
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "agent", "tool_name": "agent_create_agent",
             "arguments": json.dumps({"config": {
               "id": "wine-pairing",        # ^[a-z0-9][a-z0-9_-]{0,127}$ REJECT not coerce (bd:67qvz)
               "name": "Wine Pairing Sommelier",
               "model": "us.anthropic.claude-sonnet-4-6",
               "system_prompt": "You are a sommelier...",
               "skills": ["wine-pairing"],  # optional; gates AgentSkills only when non-empty
             }})})
# → {"ok": True, "id": "wine-pairing", "path": "..."}
```

- **Chat-callable** (czpw.1 user waiver, meta-architect `dbae0646`). `@authoring` stays as kill-switch (`SUPER_AGENT_ENABLE_AUTHORING_TOOLS`).
- **Built-in id collision** → `{"ok": False, "error": "id_collides_with_builtin"}`.
- **AgentCore seam**: `InMemoryRegistryStore` is the test backend AND the shape an AgentCore adapter slots into later.

### Step 1c: Compose + spawn + delete a sub-agent — conversationally (no restart)

bd:python-factory-czpw (children czpw.1 + czpw.2, this branch — orchestrator completions `e58afdb2` + `a0c13526`). The chat agent can now run the full CREATE → SPAWN → DELETE loop from a normal conversation, Strands-natively. Six surfaces are reachable by the chat LLM:

- **`agent_list_skills()`** (`@deterministic`, `mcp/skills_tools.py`, always-on in `server.py`) — globs `skills/*/SKILL.md` frontmatter → `{skills: [{id, name, description}], count}` (13 skills on disk today). Call it FIRST so you compose a real specialist (skills + scoped tools + prompt), not a bare prompt. The `agent_` prefix auto-passes `chat_tool_filter` — no filter edit needed.
- **`agent_create_agent(config)`** — chat-callable now (Step 1b waiver). Pass `skills[]` (ids from `agent_list_skills`) and optional `tools[]` to scope the new persona.
- **`spawn_subagent(agent_id, task)`** — native async-generator Strands `@tool` (`runtime/adapters/strands_subagent_spawn.py`). Single registered persona, SESSIONLESS. Streams the specialist inline in its OWN sub-bubble via the `tool_stream` translator branch. `include_spawn=False` on spawned sub-agents prevents recursive self-spawn.
- **`spawn_swarm(agent_ids, task)`** — native async-generator Strands `@tool` (`runtime/adapters/strands_swarm_spawn.py`, bd:python-factory-t8o1g). Assembles `strands.multiagent.Swarm` from 2+ registered personas (uses `_build_specialist` from `strands_subagent_spawn.py`), SESSIONLESS, drives via `Swarm.stream_async(task)`. Each node streams into its OWN sub-bubble via the `multiagent_node_stream` branch (G2). Use when agents should **collaborate freely** on one task.
- **`spawn_graph(agent_ids, edges, task)`** — native async-generator Strands `@tool` (`runtime/adapters/strands_graph_spawn.py`, bd:python-factory-x2k0b). Builds a `GraphBuilder → Graph` for **directed pipelines** — `edges=[{"from": id, "to": id}, ...]`; nodes with no incoming edges are auto-detected as entry points. Graceful errors on unknown ids, bad edge refs, and topology errors. Same G2 translator — each node in its own sub-bubble. Use for fixed stage order (scanner→validator, researcher→writer, etc.).
- **`agent_delete_agent(agent_id)`** (`@authoring`, `mcp/authoring.py`) — symmetric with create: rejects built-in ids, deletes config + reloads registry live; `not_found` on miss.

```python
# 1. discover skills  2. compose  3. spawn a swarm  4. spawn a graph  5. delete when done
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "agent", "tool_name": "agent_list_skills",
             "arguments": json.dumps({})})
# → {"skills": [{"id": "sast-open-scan", ...}, ...], "count": 13}

# spawn_swarm — free multi-agent collaboration
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "agent", "tool_name": "spawn_swarm",
             "arguments": json.dumps({"agent_ids": ["researcher", "writer"], "task": "..."})})

# spawn_graph — fixed pipeline: researcher feeds writer
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "agent", "tool_name": "spawn_graph",
             "arguments": json.dumps({
               "agent_ids": ["researcher", "writer"],
               "edges":     [{"from": "researcher", "to": "writer"}],
               "task":      "..."
             })})
```

All three spawn tools stream via the existing `tool_stream` rail. `spawn_subagent` yields plain agent events; `spawn_swarm` and `spawn_graph` yield `multiagent_node_stream` events (shape: `{"type": "multiagent_node_stream", "node_id": "<agent>", "event": <inner>}` — `Swarm/Graph.stream_async`, `swarm.py:867`). The G2 branch in `translate_strands_event` recurses and re-tags `message_id=f"swarm-{node_id}"` so each team member renders in its OWN sub-bubble.

> **Boundary: spawn_subagent vs spawn_swarm vs spawn_graph.** Single specialist → `spawn_subagent`. Free multi-agent collaboration on one task → `spawn_swarm`. Directed pipeline with fixed stage order → `spawn_graph` with `edges`.

> **Honest Strands coverage (strands-expert `6b9c1482` Q2 + `cc6b9e58`).** Chat now has skills discovery + composition, create/spawn-single/spawn-swarm/spawn-graph/delete, FileSessionManager, plugins, MCPClient, and FE-tool injection. Still EXECUTOR-ONLY (not chat-reachable): ContextOffloader, ConversationManager, structured output.

### Step 2: Wire your taxonomy

Pass `taxonomy_edges` to `graph_get_findings_for_run` or `graph_get_recent_findings`. Each dict matches `TaxonomyEdgeSpec` (`components/graph/src/factory/graph/runtime/models.py`).

```python
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "graph", "tool_name": "graph_get_findings_for_run",
             "arguments": json.dumps({"run_id": "wine-r-1", "taxonomy_edges": [
               {"relationship_type": "TASTED_AS", "target_label": "Varietal",
                "target_props": {"id": "varietal_id", "name": "varietal_name"}}]})})
```

`taxonomy_edges=None` → back-compat security CWE/OCSF defaults. `taxonomy_edges=[]` → no join. Custom edges drive caller-supplied row columns from `target_props`.

### Step 3: Drive your RL loop

Pass `config={"domain_class": "<your_domain>", ...}` to `games_create`. `_store_learnings` reads `domain_class` (fallback: `vuln_class → game_type`) and dual-emits memory tags: `[domain_class, "scan-learnings", f"{domain_class}-learnings", run_id]`. Security flows (`scan-learnings`) stay intact; per-domain recall (`{domain_class}-learnings`) lights up automatically.

```python
# Direct MCP arg — drive the RL loop from outside games_create
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={"brick_name": "games", "tool_name": "games_process_workflow_rl",
             "arguments": json.dumps({
               "graph_id": "wine-pairing-r-1", "run_id": "wine-r-1",
               "domain_class": "wine_pairing",
               "count_labels": ["WinePairing", "VarietalMatch"],
               "taxonomy_edges": [{"relationship_type": "TASTED_AS",
                                   "target_label": "Varietal",
                                   "target_props": {"id": "varietal_id"}}],
               "workflow_type": "auto", "target_app": "wine-cellar",
             })})
```

`DEFAULT_COUNT_LABELS = ("Finding", "ProvenExploit")` keeps the security default. Substrate scope: `domain_class` / `count_labels` / `taxonomy_edges` flow through `games_process_workflow_rl`, `games_write_experiment_report`, `graph_get_workflow_summary`, `evals_persist_score`, `LearningEventPayload.domain_class`, and `mcp_utils.correlation._CANONICAL_KEYS`.

### Step 4: Flip the chat persona

```bash
export COMPANION_X_CHAT_AGENT_ID=wine-pairing
uv run python -m factory.api.main
```

Cache key + `Agent.name` + `FileSessionManager.session_id` all use `f"{agent_id}-{thread_id}"`, so swapping the env yields a clean session boundary — no history bleed across personas. A typo in the env triggers LOUD-FAIL at chat boot per strands-expert verdict `9b6d46cd`; do not silently fall back to `the control-plane runtime-default`.

The env is the **default** persona (used when the FE sends no selector). It is byte-identical to pre-d4roe behavior when `forwardedProps` is absent (`a19ef414` Q4).

### Step 4b: Switch persona per-thread from the `/` palette (no restart, no env)

bd:python-factory-d4roe.3. The FE palette (`frontends/next-dashboard/components/chat/persona-palette.tsx`) lists personas from `GET /api/personas` (thin passthrough to `agent_get_agent_registry`, mounted in `bridge.py`). On pick, `core.setProperties({companion_x_agent_id: id})` carries the selection in `RunAgentInput.forwardedProps.companion_x_agent_id` on the next run. `ag_ui_input.py::parse_agent_id` pulls it out; `_get_or_create(thread_id, agent_id)` resolves via `unified_personas`. `agent_id=None` falls back to the `COMPANION_X_CHAT_AGENT_ID` env default (byte-identical, `a19ef414` Q4). `close(thread_id)` drops ALL `*-{thread_id}` slots (`a19ef414` Q5-i). Registry miss → `ValueError` → terminal `ErrorEvent` → `RUN_ERROR`. Resolution and error handling live in the adapter, not the base.

### Step 5: Wire your taxonomy

bd:python-factory-qm07q. `register_extension(domain_id, *, node_types, relationship_types, conventions=None)` — module-global, append-only, raises `ValueError` on collision.

```python
from factory.graph.runtime.taxonomy_registry import register_extension
register_extension("wine_pairing",
  node_types={"Varietal": {"properties": {"id": "str", "name": "str"}}},
  relationship_types={"TASTED_AS": {"from_label": "WinePairing", "to_label": "Varietal"}})
```

`graph://schemas/taxonomy/{domain}` resolves: registered → security base + extension merged; `security` → `SECURITY_TAXONOMY` byte-identical; unknown → 404-shape JSON with `available_domains`. `reset_extensions()` is test-only.

### Step 6: Scope your recall

`memory_retrieve` accepts `tags: list[str] | None = None` (bd:lin6p) and `metadata: dict[str, str] | None = None` (bd:b2d2o). Trinary: `None` = no filter; `[]` = match nothing; non-empty = ANY-match. `metadata={}≡None` (asymmetric vs `tags=[]`). Cross-filter: `tags ∧ metadata` = intersection. Tier-1 native push-down on `neo4j` + `neo4j_embedding`.

```python
call_brick_tool(brick_name="memory", tool_name="memory_retrieve", arguments=json.dumps({
  "user_id": "kiro-agent", "query": "varietal pairing patterns",
  "tags": ["wine_pairing-learnings"], "metadata": {"run_id": "wine-run-1"},
  "limit": 5,
}))
```

Per-agent recall lights up automatically — `LearningRecallPlugin(agent)` reads `self._agent.agent_id` and forwards `tags=[f"{agent_id}-learnings"]` when non-default (bd:ziwqs). The chat adapter binds `agent_id=cfg.id` to the Strands `Agent` ctor — that bind was missing pre-ziwqs so recall was structurally broken.

### Step 7: Sanitize metadata keys (Cypher injection guard)

Cypher property names cannot be parameterized. The substrate enforces `^[a-zA-Z_][a-zA-Z0-9_]*$` at TWO sites: `MemoryQuery._validate_metadata_keys` (Pydantic) AND `_neo4j_filters.safe_property_key` (adapter). Both use `re.fullmatch` — `re.match` accepts trailing `\n`/`\r`/`\t` (QA bypass discovered and fixed in the same wave, bd:b2d2o, verdict `f279063c` Q7-SECURITY).

## Known Gaps / SDK Notes

**`AgentSkills` must use `plugins=` at ctor time (bd:python-factory-t8o1g).** `AgentSkills` is a `Plugin` (implements `init_agent`), NOT a `HookProvider` (implements `register_hooks`). Calling `hooks.add_hook(skills_plugin)` invokes `register_hooks`, which crashes on `Plugin` instances. The correct SDK path is `Agent(plugins=[skills_plugin])` at constructor time — Strands routes through `_PluginRegistry.add_and_init → init_agent → _register_hooks` (walks `@hook` methods via `plugin.hooks`). Fixed in both `_build_specialist` (`strands_subagent_spawn.py`) and `StrandsMCPChatAgent._get_or_create` (`strands_mcp_chat.py`): `skills_plugin = build_skills_plugin(cfg.skills)` is built BEFORE the `Agent` ctor and passed as `plugins=[skills_plugin] if skills_plugin is not None else None`.

**`multiagent_node_stream` translator (G2, bd:python-factory-t8o1g).** `Swarm.stream_async` and `Graph.stream_async` yield `multiagent_node_*` event shapes (DIFFERENT from the plain `Agent.stream_async` shapes). `translate_strands_event` grew the G2 branch: `raw.get("type") == "multiagent_node_stream"` → recurse into `raw["event"]`, re-tag `message_id=f"swarm-{node_id}"`. `multiagent_node_start` / `multiagent_node_stop` carry no text deltas and fall through to no-op. Without G2, all swarm/graph node output would be silently dropped (same class of bug as the original `tool_stream` gap in czpw.1).

**`ContextOffloader` process-wide dir + `cleanup_offload_dir()` (bd:python-factory-9m5e3).** `_build_specialist` attaches a `ContextOffloader(FileStorage(artifact_dir=_offload_dir()))` to every spawned sub-agent. `_offload_dir()` is a module-level singleton — one `/tmp/strands-offload-*` directory per process rather than one per `spawn_*` call (strands-expert verdict `fe209c0c` Q3). `cleanup_offload_dir()` (exported in `strands_subagent_spawn.__all__`) tears down that directory via `shutil.rmtree(ignore_errors=True)` and resets the singleton. **Wire it to your shutdown hook** (e.g. `StrandsMCPChatAgent.close` or a `lifespan` handler in `factory.api.main`) to avoid leaking `/tmp/strands-offload-*` directories across restarts. Safe to call multiple times; no-ops when the directory was never created.

## Success Criteria

- [ ] `AgentConfig` for your domain appears in `AGENTS_TYPED` after import.
- [ ] `COMPANION_X_CHAT_AGENT_ID=<your-id>` boots the API without a LOUD-FAIL.
- [ ] Chat sidebar reflects your `system_prompt` (a domain-specific question gets a domain-specific answer).
- [ ] `graph_get_findings_for_run` with your `taxonomy_edges` returns rows with your domain columns.
- [ ] `read_brick_resource` of `graph://schemas/taxonomy/<your_domain>` returns base+extension merged JSON; `security` returns `SECURITY_TAXONOMY` byte-identical; unknown returns 404-shape JSON with `available_domains`.
- [ ] `games_create` with `config={"domain_class": "<your_domain>", ...}` results in a `memory_store` whose tags include `f"{your_domain}-learnings"` (verifiable via `memory_retrieve` with that tag).
- [ ] `memory_retrieve(... tags=[f"{your_domain}-learnings"])` returns only your domain's memories; `tags=[]` returns nothing (strict empty); `tags=None` keeps today's behavior.
- [ ] Existing security flows still work — `scan-learnings` recall is preserved (dual-emit). Per-agent recall (bd:python-factory-ziwqs, retracts zj026) lights up automatically: `LearningRecallPlugin` forwards `tags=[f"{agent.agent_id}-learnings"]` when `agent_id` is non-default; `'default'`/empty omits the filter (broad recall byte-identical).

## API Reference

| Brick | Import | Key Symbols |
|-------|--------|-------------|
| agent | `factory.agent.runtime.registry_contracts` | `AgentConfig(id, name, model, system_prompt, tools, skills, description)` (Pydantic, `extra="forbid"`); `id` charset-locked `^[a-z0-9][a-z0-9_-]{0,127}$` (REJECT not coerce, bd:67qvz). No `domain_class` field — `cfg.id` IS the recall namespace (bd:ziwqs). |
| agent | `factory.agent.runtime.ports` | `RegistryStore` Protocol: `load_personas()`, `save_persona(config)`, `delete_persona(agent_id) -> bool`. DATA tier only; built-ins stay in `AGENTS_TYPED`. |
| agent | `factory.agent.runtime.adapters.registry_store` | `DiskRegistryStore(config_dir)` — local dev; `InMemoryRegistryStore` — test + AgentCore seam. |
| agent | `factory.agent.registry.unified` | `unified_personas() -> list[AgentConfig]`; `merge_personas(builtins, store)` (built-in-wins); `set/get/reset_default_store`. |
| agent | `factory.agent.runtime.adapters` | `skills_attach.build_skills_plugin(skills)`; `strands_mcp_chat_persona.resolve_agent_config(id)` (LOUD-FAIL on miss); `StrandsMCPChatAgent._get_or_create(thread_id, agent_id=None)` → `Agent(agent_id=cfg.id, plugins=[skills_plugin], ...)`; `close(thread_id)` drops ALL `*-{thread_id}` slots. |
| agent | `factory.agent.runtime.adapters.strands_subagent_spawn` | `spawn_subagent(agent_id, task)` @tool; shared `_build_specialist(cfg)` + `_text_event(msg)` helpers (used by swarm + graph spawn modules). |
| agent | `factory.agent.runtime.adapters.strands_swarm_spawn` | `spawn_swarm(agent_ids, task)` @tool; `Swarm(nodes=[...])` SESSIONLESS (`swarm.py:238`). |
| agent | `factory.agent.runtime.adapters.strands_graph_spawn` | `spawn_graph(agent_ids, edges, task)` @tool; `GraphBuilder.add_node/add_edge/build()`; `edges=[{"from":id,"to":id}]`. |
| agent | `factory.agent.runtime.adapters.strands_registered_graph_spawn` | `spawn_registered_graph(graph_id, task)` @tool; resolves `GraphConfig` from `get_default_graphs()`; only `AgentNodeRef` nodes (`type="agent"`) supported. |
| agent | `factory.agent.runtime.adapters.strands_mcp_chat_persona` | `build_chat_tools(mcp_client, *, include_spawn=True)` — appends `spawn_subagent`, `spawn_swarm`, `spawn_graph` when `True`. |
| agent | `factory.agent.runtime.adapters.strands_mcp_chat_stream` | `translate_strands_event(raw, message_id)` — `tool_stream` branch (czpw.1, `subagent-{tcid}`); G2 `multiagent_node_stream` branch (t8o1g, `swarm-{node_id}`). |
| agent | `factory.agent.plugins.LearningRecallPlugin` | reads `self._agent.agent_id` at invocation (`strands/agent/agent.py:227`); `tags=[f"{agent_id}-learnings"]` when non-default; `'default'`/empty → no filter. |
| api base | `bases/api/.../ag_ui_input.py` | `parse_agent_id(forwarded_props) -> str\|None`; transport shell only, no resolution. |
| graph | `factory.graph.runtime.models.TaxonomyEdgeSpec` | `relationship_type`, `target_label`, `target_props` (Pydantic). |
| graph | `factory.graph.runtime.taxonomy_registry` | `register_extension(domain_id, *, node_types, relationship_types, conventions=None)` — raises `ValueError` on collision. `resolve_domain_taxonomy(domain_id)` → security default / merged extension / `None`. `reset_extensions()` test-only. |
| games | `factory.games.runtime` | `DEFAULT_COUNT_LABELS = ("Finding", "ProvenExploit")`; `_collect_findings(invoker, run_id, wtype, count_labels=None, taxonomy_edges=None)`. |
| memory | `factory.memory.runtime.models.MemoryQuery` | `tags:list[str]\|None`; `metadata:dict[str,str]\|None` (AND-join, `{}≡None` asymmetric); `_validate_metadata_keys` + `_neo4j_filters.safe_property_key` — both `re.fullmatch` `^[a-zA-Z_][a-zA-Z0-9_]*$`. |

## MCP Tools

| Tool | Brick | Description |
|------|-------|-------------|
| `agent_create_agent` | agent | `@authoring` (d4roe.2; chat-callable per czpw.1 user waiver, meta-architect `dbae0646`). Args: `config:dict` (`id`, `name`, `model`, `system_prompt`, `skills`, `tools`, `description`). `write_yaml_config + agent_registry.load()` → resolvable with NO restart. Rejects built-in id collisions. Gated by `SUPER_AGENT_ENABLE_AUTHORING_TOOLS`. Returns `{ok, id, path}`. |
| `agent_get_agent_registry` | agent | `@deterministic`. Unified merge (built-ins + store). Backs `GET /api/personas`. |
| `agent_delete_agent` | agent | `@authoring` (czpw.2). Rejects built-in ids; `delete_yaml_config + agent_registry.load()`. Returns `{ok, id}`; `{ok:False, error:"not_found"}` on miss. |
| `agent_list_skills` | agent | `@deterministic` (czpw.2). Globs `skills/*/SKILL.md` → `{skills:[{id,name,description}], count}` (13 on disk). Always-on. |
| `spawn_subagent` (native `@tool`, NOT MCP) | agent runtime | bd:python-factory-czpw.1, strands-expert `209fb838`. NOT on the MCP aggregator — a Strands async-generator `@tool` (`runtime/adapters/strands_subagent_spawn.py`) appended to the chat agent's tool list via `build_chat_tools(mcp_client, include_spawn=True)`. Args: `agent_id: str, task: str`. Resolves a persona via `unified_personas`, builds a SESSIONLESS Strands `Agent` (scoped tools, `agent_id=cfg.id`, skills plugin), streams `specialist.stream_async(task)` back inline (own bubble via the `tool_stream` translator branch). `include_spawn=False` on sub-agents blocks recursive self-spawn. Unknown id → graceful text listing. |
| `spawn_swarm` (native `@tool`, NOT MCP) | agent runtime | bd:python-factory-t8o1g, strands-expert `cc6b9e58`. Args: `agent_ids: list[str], task: str`. Assembles `strands.multiagent.Swarm` from registered personas (reuses `_build_specialist` from `strands_subagent_spawn.py`), SESSIONLESS, drives via `Swarm.stream_async(task)`. Each node streams in its OWN sub-bubble via the `multiagent_node_stream` G2 branch (`message_id=f"swarm-{node_id}"`). Unknown/empty `agent_ids` → graceful text listing. Use for free multi-agent collaboration. |
| `spawn_graph` (native `@tool`, NOT MCP) | agent runtime | bd:python-factory-x2k0b, strands-expert `0bf122e1`. Args: `agent_ids: list[str], edges: list[dict], task: str`. `edges` shape: `[{"from": id, "to": id}, ...]`; nodes with no incoming edges auto-detected as entry points. Uses `GraphBuilder.add_node` + `add_edge` + `build()` → `Graph.stream_async(task)`. Graceful errors: unknown ids → text; bad edge refs → text; `build()` `ValueError` → text. Same G2 translator as `spawn_swarm`. Use for fixed-stage pipelines (scanner→validator, researcher→writer). |
| `spawn_registered_graph` (native `@tool`, NOT MCP) | agent runtime | bd:python-factory-4bqcz. Args: `graph_id: str, task: str`. Like `spawn_graph` but resolves topology from the built-in graph registry (`get_default_graphs`) by `graph_id` — no inline node+edge description required. Runs the 17+ pre-built pipelines (redteam, recon, sandbox, sast, dast, etc.) conversationally. Call `agent_get_graph_registry()` first to list available ids. Only `AgentNodeRef` nodes (`type="agent"`) are mapped to live Strands `Agent` instances via `_build_specialist`; `SwarmNodeRef` / `GraphNodeRef` shapes yield a graceful text error. Unknown `graph_id` yields a text listing of known graph ids (never raises). Reuses `_build_specialist` from `strands_subagent_spawn.py` — same SESSIONLESS, scoped-tools, `SummarizingConversationManager` (bd:python-factory-mqhta) path as the other spawn tools. |
| `graph_get_findings_for_run` | graph | `@deterministic`. Args: `run_id, app="", limit=50, taxonomy_edges:list[dict]\|None=None`. `None` = security CWE/OCSF defaults; `[]` = no taxonomy join; custom edges drive row columns. |
| `graph_get_recent_findings` | graph | `@deterministic`. Args: `severity="", app="", run_id="", limit=50, taxonomy_edges:list[dict]\|None=None`. Same semantics. |
| `graph_get_workflow_summary` | graph | `@deterministic`. Args: `run_id, taxonomy_edges:list[dict]\|None=None, count_labels:list[str]\|None=None`. Composes per-label counts + Finding verdict histogram + `target_app` from the typed primitives; both polymorphic args forward into the underlying calls. |
| `graph_count_entities_by_run` | graph | `@deterministic`. Args: `run_id, labels:list[str]`. Domain-agnostic counter — pair with games `count_labels` for per-domain RL counters. |
| `games_create` | games | `@operational`. Pass `config={"domain_class": "<your_domain>", "run_id": "...", ...}` to drive the RL pipeline's domain tagging. |
| `games_process_workflow_rl` | games | `@operational`. Args: `graph_id, run_id, vuln_class="", domain_class="", count_labels:list[str]\|None=None, taxonomy_edges:list[dict]\|None=None, workflow_type="auto", target_app="", session_id=""`. Memory tags dual-emit `[domain_class, "scan-learnings", f"{domain_class}-learnings", run_id]`. |
| `games_write_experiment_report` | games | `@operational`. Same `domain_class` / `count_labels` / `taxonomy_edges` triple as `games_process_workflow_rl`, plus reporting fields (`framework`, `agent_count`, `duration_seconds`, `extra_metrics`). |
| `evals_persist_score` | evals | `@operational`. Args include `domain_class:str=""` (bd:python-factory-tmlrx) — persisted alongside `vuln_class` for longitudinal queries via `storage_doc_query` against the sqlite `eval_results` collection. |
| `memory_retrieve` | memory | `@operational`. Args: `query, user_id=None, memory_type=None, category=None, min_relevance=0.3, limit=5, tags: list[str] \| None = None, metadata: dict[str, str] \| None = None`. **lin6p (PR #611)**: `tags=None` = no filter; `tags=[]` = match nothing (strict empty); non-empty = ANY-match on `metadata.tags`. **b2d2o (this PR)**: `metadata` per-key AND-join; `None` AND `{}` BOTH = no filter (asymmetric vs `tags=[]` — by design, verdict `f279063c` Q4). Cross-filter `tags ∧ metadata` = intersection. Tier-1 native push-down on `neo4j` + `neo4j_embedding` (bd:26e2a + b2d2o); Tier-2/3 inherit runtime post-filter. Metadata keys MUST match `^[a-zA-Z_][a-zA-Z0-9_]*$` (Cypher injection guard at Pydantic + adapter boundaries). |

## MCP Resources

| URI | Brick | Description |
|-----|-------|-------------|
| `graph://schemas/taxonomy/{domain}` | graph | **NEW from this PR (bd:python-factory-qm07q).** Per-domain taxonomy view. `{domain}=security` returns `SECURITY_TAXONOMY` verbatim (byte-identical, pinned by canary). Registered extensions (via `factory.graph.runtime.taxonomy_registry.register_extension(...)`) return security base merged with their `node_types` / `relationship_types` / `conventions`. Unknown domains return 404-shape JSON `{"error": ..., "available_domains": ["security", ...]}` — never raises. |
| `graph://schemas/taxonomy` | graph | Unified graph taxonomy (security default, back-compat). |
| `graph://schemas/security-taxonomy` | graph | Focused security pipeline view (back-compat alias for the security default). |

## HTTP Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/personas` | **bd:python-factory-d4roe.3.** Thin read passthrough to `agent_get_agent_registry` (mounted in `bases/api/.../runtime/bridge.py::list_personas`). Returns `{"personas": [...], "count": N}`; a non-list tool result defensively yields `{"personas": [], "count": 0}`. The api base owns no persona data of its own (verdict `a19ef414` Q3). Consumed by the FE `/` persona palette. |

## Tested invariants (key canaries)

- `the control-plane runtime-default.system_prompt == COMPANION_X_PROMPT` byte-for-byte (`test_chat_persona_registry.py`).
- Cache slots differentiate two threads with the same `thread_id` + different `agent_id` (`test_chat_persona_cache_key.py`).
- `taxonomy_edges=None` → legacy CWE/OCSF Cypher shape; `taxonomy_edges=[]` → no OPTIONAL MATCH (`test_neo4j_taxonomy_edges.py`).
- `DEFAULT_COUNT_LABELS == ("Finding", "ProvenExploit")` (`test_count_labels_substrate.py`).
- `domain_class` wins over `vuln_class`; tag set always carries `{domain}-learnings` + back-compat `scan-learnings` (`test_domain_class_substrate.py`).
- `graph://schemas/taxonomy/security` returns `SECURITY_TAXONOMY` byte-identical; unknown domain returns 404-shape with `available_domains` (`test_taxonomy_registry.py`, `test_taxonomy_resource_template.py`).
- `tags=None` back-compat; `tags=[]` matches nothing; `tags=[x,y]` ANY-match (`test_retrieve_tags_filter.py`).
- `metadata=None ≡ metadata={}` (no filter, asymmetric vs `tags=[]`); cross-filter `tags ∧ metadata` = intersection; Pydantic + adapter `re.fullmatch` guard (`test_retrieve_metadata_filter.py`, `test_metadata_safe_key.py`).
- `LearningRecallPlugin(agent)` reads `agent.agent_id` at invocation; non-default `agent_id` → `tags=[f"{agent_id}-learnings"]`; `'default'`/empty → no filter (`test_per_domain_recall_e2e.py`).

## File map

```
components/agent/src/factory/agent/
├── registry/{defaults.py,defaults_companion_x.py,defaults_<domain>.py}         # AGENTS_TYPED
├── registry/{unified.py,agents.py}                                              # unified_personas, AgentRegistry
├── runtime/{ports.py,registry_contracts.py}                                     # RegistryStore Protocol; AgentConfig id validator
├── runtime/adapters/{registry_store.py,skills_attach.py,strands_mcp_chat*.py}  # Disk/InMemory store; build_skills_plugin; chat adapter
├── runtime/adapters/strands_subagent_spawn.py                                   # spawn_subagent @tool + shared _build_specialist/_text_event + cleanup_offload_dir (9m5e3)
├── runtime/adapters/strands_swarm_spawn.py                                      # spawn_swarm @tool (t8o1g)
├── runtime/adapters/strands_graph_spawn.py                                      # spawn_graph @tool (x2k0b)
├── runtime/adapters/strands_registered_graph_spawn.py                          # spawn_registered_graph @tool (4bqcz)
├── runtime/adapters/strands_mcp_chat_stream.py                                  # translate_strands_event: tool_stream branch + G2 multiagent_node_stream
├── mcp/authoring.py                                                             # agent_create_agent + agent_delete_agent
└── mcp/skills_tools.py                                                          # agent_list_skills

components/graph/src/factory/graph/
├── runtime/{models.py,taxonomy_registry.py,adapters/}                          # TaxonomyEdgeSpec; 5 public registry funcs; Cypher builders
└── mcp/{deterministic_typed.py,resources.py}                                   # typed reads + graph://schemas/taxonomy/{domain}

components/memory/src/factory/memory/
├── runtime/{models.py,runtime.py,adapters/_neo4j_filters.py}                   # MemoryQuery.{tags,metadata}; build_filter_clauses; safe_property_key
└── mcp/operational.py                                                           # memory_retrieve(tags=, metadata=)
```

## Smoke

```bash
# spawn tools
uv run pytest components/agent/test/factory/agent/test_strands_swarm_spawn.py components/agent/test/factory/agent/test_strands_graph_spawn.py components/agent/test/factory/agent/test_strands_mcp_chat_stream_swarm.py -v

# persona + cache-key
uv run pytest components/agent/test/factory/agent/test_chat_persona_registry.py components/agent/test/factory/agent/test_chat_persona_cache_key.py -v

# taxonomy_edges + taxonomy registry
uv run pytest components/graph/test/factory/graph/test_neo4j_taxonomy_edges.py components/graph/test/factory/graph/test_taxonomy_registry.py components/graph/test/factory/graph/test_taxonomy_resource_template.py -v

# memory filters + Cypher injection guard
uv run pytest components/memory/test/factory/memory/test_retrieve_tags_filter.py components/memory/test/factory/memory/test_retrieve_metadata_filter.py components/memory/test/factory/memory/test_metadata_safe_key.py components/memory/test/factory/memory/test_tags_pushdown_neo4j.py -v

# per-agent recall (ziwqs)
uv run pytest components/agent/test/factory/agent/test_per_domain_recall_e2e.py components/agent/test/factory/agent/test_chat_persona_domain_class_e2e.py -v

# d4roe — unified registry, runtime authoring, per-thread persona
uv run pytest components/agent/test/factory/agent/test_unified_registry_properties.py components/agent/test/factory/agent/test_agent_create_agent_tool.py components/agent/test/factory/agent/test_chat_persona_switch_d4roe.py -v
```

## Phase landings

| bd | Landed |
|---|---|
| `hadbi.1` | Phase 2 — chat persona via agent registry; `AgentConfig.skills` field (PR #599) |
| `ecph9` | Phase 3 — graph typed reads via `taxonomy_edges` (PR #599) |
| `qer1z` | Phase 4 — games RL `domain_class` + `count_labels` (PR #599) |
| `twxj0`…`ttru9` | Follow-up wave — domain/count/taxonomy through MCP boundary, LearningEventPayload, per-node skills (PRs #600/#601) |
| `qm07q` / `lin6p` | P3 wave 1 — graph per-domain taxonomy registry + `memory_retrieve` tags filter (PR #611) |
| `26e2a` / `b2d2o` / `nley3` | P3 wave 2 — Tier-1 tags push-down, metadata AND-filter, re.fullmatch injection guard |
| `ziwqs` | P3 wave 3 — drop domain_class field; agent_id IS the recall namespace (43 targeted PASS, 1399 regression PASS) |
| `d4roe.1` (`8c2bd674`) | Unified persona registry — `RegistryStore` Protocol, `DiskRegistryStore` / `InMemoryRegistryStore`, `unified_personas` single read path |
| `d4roe.2` (`a4221680`) | `agent_create_agent` `@authoring` tool — write_yaml_config + reload, no restart |
| `67qvz` (`5148afe1`) | `AgentConfig.id` charset-locked `^[a-z0-9][a-z0-9_-]{0,127}$` REJECT not coerce |
| `d4roe.3` (`a4b0be66`) | Per-thread persona switch via `forwardedProps.companion_x_agent_id`; `GET /api/personas`; FE persona palette |
| `czpw.1` (`e58afdb2`) | NEW `spawn_subagent` native @tool + tool_stream translator branch; `agent_create_agent` un-gated for chat (user waiver, meta-architect `dbae0646`) |
| `czpw.2` (`a0c13526`) | NEW `agent_delete_agent` + `agent_list_skills`; prompt updated; `agent_launch_swarm` guidance removed |
| `t8o1g` | NEW `spawn_swarm` + multiagent_node_stream G2 translator; AgentSkills plugins= fix |
| `x2k0b` | NEW `spawn_graph` (GraphBuilder directed pipeline) |
| `4bqcz` | NEW `spawn_registered_graph` native @tool — registry-driven graph spawn, no inline topology (`strands_registered_graph_spawn.py`) |
| `mqhta` | `_build_specialist` now attaches `SummarizingConversationManager` per sub-agent so each specialist compresses its own rolling context independently of the parent thread |
| `9m5e3` | `cleanup_offload_dir()` exported from `strands_subagent_spawn.py` — process-wide offload dir teardown wired to `StrandsMCPChatAgent.close` / process shutdown |
