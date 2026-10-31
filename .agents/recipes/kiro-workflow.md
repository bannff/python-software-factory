# Kiro-Orchestrated Workflow — Master Recipe

Kiro acts as the deterministic orchestrator, dispatching sub-agents for each phase.
Each sub-agent has access to the control-plane runtime power for all 38 bricks via MCP.

## Architecture

Unlike Strands where the LLM decides handoffs (swarm) or the graph engine manages
parallelism (graph), Kiro makes routing decisions deterministically based on
sub-agent results. Sub-agents write to Neo4j graph during execution (not after).

## Skills (in .kiro/skills/)

| Skill | Phase | Description |
|-------|-------|-------------|
| kiro-sast-scanner | SAST scan | Reads code, finds vulns, writes SuspectedVuln to graph |
| kiro-sast-consolidator | SAST merge | Queries graph, deduplicates, applies voting consensus |
| kiro-sast-validator | SAST validate | Adversarially challenges findings, updates verdicts |
| kiro-recon-lead | Recon | Discovers infra via graph tools, writes to graph |
| kiro-recon-verifier | Recon verify | Cross-checks discoveries, fills gaps |
| kiro-sandbox-setup | Sandbox | Provisions profile-based container, verifies health, stores SandboxEnv in graph |
| kiro-dast-tester | DAST | Tests running app via HTTP, stores proven exploits |

## Workflow Types

### SAST Scan (kiro-sast)
1. Dispatch `security-engineer` as Scanner A → SuspectedVuln entities (dataflow focus)
2. Dispatch `security-engineer` as Scanner B → SuspectedVuln entities (authz focus)
3. Dispatch `security-engineer` as Consolidator → deduplicated Finding entities
4. Dispatch `security-engineer` as Validator → verdicts (CONFIRMED / REJECTED)
5. Post-workflow pipeline (RL scoring, evals, metrics, GT expansion)

### Sandbox Setup (kiro-sandbox)
1. Dispatch `security-engineer` as Sandbox Setup Agent → env_id, health status
2. Verify target is responding
3. Store SandboxEnv in graph for downstream workflows

### DAST Scan (kiro-dast)
1. Run Sandbox Setup workflow first (or reuse existing SandboxEnv from graph)
2. Dispatch `security-engineer` as DAST Tester → ProvenExploit entities
3. Post-workflow pipeline

## Workflow-Specific Recipes

- `kiro-sast-workflow.md` — Full SAST pipeline with post-workflow loop
- `kiro-sandbox-workflow.md` — Sandbox provisioning and health verification
- (TODO) `kiro-dast-workflow.md` — DAST pipeline
- (TODO) `kiro-recon-workflow.md` — Recon pipeline

## Post-Workflow Pipeline (ALL workflows)

After the domain-specific phases complete, trigger:
1. `games_process_workflow_rl` — GT scoring, blockchain reward, memory learnings
2. `evals_evaluate_multi` — LLMAJ grading (faithfulness, tool_selection, goal_success)
3. `metrics_record` — precision, recall, f1, duration per run
4. `security_ingest_gt_entry` — novel findings proposed as new GT entries
5. Loop check — if F1 < threshold, re-dispatch with updated context

## Advantages Over Strands
- Fresh context per sub-agent (no context window overflow)
- Deterministic consolidation (code-level set intersection)
- Full Kiro tool access (filesystem, shell, web, all MCP powers)
- No Bedrock dependency for orchestration layer
- Access to workspace steering files and project knowledge

## Limitations vs Strands
- Sequential only (no parallel sub-agent dispatch)
- No model diversity (all sub-agents use Kiro's model)
- No shared mutable state during execution
- No streaming events during sub-agent execution

## Report Format
Same JSON schema as Strands runs. Workflow type: `kiro`.
Output: `projects/the control-plane project/challenges/experiments/{run_id}.json`
