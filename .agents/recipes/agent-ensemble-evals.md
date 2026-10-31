# Recipe: Agent Ensemble Evals (Strands SOP + Experiment + Simulation)

Systematically evaluate a specialized security catalog using Strands Evals features. IDOR is one domain recipe, not static team ownership; the normative control-plane split lives in [`.agents/steering/factory-protocol.md`](../../.agents/steering/factory-protocol.md).

Freeze evaluation policy before execution. Evals owns immutable evidence-bound reports, typed deficiencies, acceptance, and promotion; agents cannot provide executable validators or alter criteria after seeing results. A registered Agent Graph may perform bounded research/synthesis/revision within one attempt, while Workflow journals attempts and enforces global budgets, retries, and stopping. Use Swarm only for bounded exploratory collaboration.

## Context

This specialized recipe evaluates a current legacy IDOR catalog spanning Recon → Sandbox Setup → SAST → DAST. The listed groups are candidates under evaluation, not evidence-promoted templates or permanent team ownership; the control-plane runtime may assemble the smallest bounded objective team through Agent surfaces. The catalog demonstrates:
- Ensemble Diversity (different models per role)
- Disagreement Resolution (2/3 voting consensus)
- Execution Grounding (agents must cite sources)
- Structured Reflection (Generate → Critique → Refine)
- Adversarial Self-Validation (agent argues against its own findings)
- Eval Feedback Loop (evals integrated into workflow)

## Bricks Used
- `evals` — SOP workflow, experiments, simulations, LLMAJ evaluators
- `agent` — Registry of swarm/graph agent definitions

## Prerequisites
- AWS credentials (Strands evaluators + ExperimentGenerator call Bedrock)
- Agent source code accessible (system prompts, tool lists, graph/swarm configs)

## What Strands Features Actually Do

**Eval SOP** — A guided evaluation design process. An AI assistant may propose cases, rubrics, and evaluator selections, while Evals executes only registered, allowlisted validators under policy frozen before the run. The process:
1. Reads the agent's actual code/config and proposes an evaluation design
2. Proposes domain-specific test cases covering normal operations, edge cases, and failure modes
3. Resolves the proposal to registered evaluators and has Evals execute the frozen evaluation policy
4. Produces an immutable evidence-bound report with typed deficiencies and improvement recommendations

**ExperimentGenerator** — A test case factory. You describe context, it auto-generates
diverse test cases with rubrics at varying difficulty levels. Independent from SOP.

**ActorSimulator** — A synthetic user. Creates a persona-driven user that has a
multi-turn conversation with your agent, pushing toward a goal. Tests conversational
quality and goal completion.

## The Correct 8-Step Workflow (per agent)

```
Step 1: SOP Phase 1 — PLAN
  Feed the agent's ACTUAL source code (system prompt, tools, graph config)
  to evals_sop_plan. Get: recommended evaluators, success criteria, risk assessment.

Step 2: SOP Phase 2 — GENERATE TEST DATA
  evals_sop_generate_data creates domain-specific test cases from the plan.

Step 3: SOP Phase 3 — RUN EVAL
  evals_sop_run executes the agent against test cases with recommended evaluators.
  Scores each case. Records judge reasoning.

Step 4: SOP Phase 4 — REPORT
  evals_sop_report produces failure patterns and improvement recommendations.

Step 5: IMPROVE THE AGENT
  Apply the SOP recommendations: fix prompts, swap models, add grounding rules,
  adjust tool access. Document what changed and why.

Step 6: RE-RUN SOP TO VERIFY
  Run Steps 1-4 again on the improved agent. Compare scores.
  Did the improvements work? Record delta.

Step 7: EXPERIMENT (independent coverage)
  evals_generate_experiment + evals_run_experiment with fresh test cases
  the SOP hasn't seen. Tests generalization beyond the SOP's test suite.

Step 8: SIMULATION (multi-turn interaction)
  evals_run_simulation with ActorSimulator using stage-specific actor profiles.
  Tests whether the agent is useful in a real conversation.
```

## Why All 8 Steps Matter

SOP (Steps 1-4) designs a proper evaluation and tells you WHERE the agent fails.
Improvement (Step 5) fixes the failures. Re-run (Step 6) verifies the fixes worked.
Experiments (Step 7) test generalization — can the improved agent handle novel inputs?
Simulation (Step 8) tests usability — can a human/agent actually work with it?

Without Step 5-6, you have a snapshot but no iteration loop.
Without Step 7, you might overfit to the SOP's test cases.
Without Step 8, you might have a correct but unusable agent.

## Current Security Catalog (Specialized, Not Team Ownership)

These entries record one current legacy security catalog under evaluation. the control-plane runtime may assemble a smaller objective-specific team dynamically; this table neither assigns static team ownership nor claims evidence-based promotion.

| Stage | Workflow | Agent | Model | Role |
|-------|----------|-------|-------|------|
| Recon | rt-recon | recon-lead | Haiku 4.5 | Query the graph, write the graph |
| Recon | rt-recon | recon-verify | Nova 2 Lite | Cross-check, fill gaps |
| Recon | rt-recon | recon-summary | GPT OSS | Consolidate into ReconSummary |
| Artifacts | rt-pull-artifacts | artifact-puller | Haiku 4.5 | Read code packages |
| Artifacts | rt-pull-artifacts | artifact-reviewer | Sonnet 4.6 | Review for secrets/misconfigs |
| Artifacts | rt-pull-artifacts | artifact-summary | GPT OSS | Summarize findings |
| Sandbox | rt-setup-sandbox | cfn-builder | Sonnet 4.6 | Build CFN from graph |
| Sandbox | rt-setup-sandbox | deployer | Haiku 4.5 | Deploy to LocalStack |
| Sandbox | rt-setup-sandbox | deploy-verify | Scout | Validate deployment |
| SAST | rt-sast-scan | gptoss-sast | GPT OSS | SAST scanner (parallel) |
| SAST | rt-sast-scan | sonnet-sast | Sonnet 4.6 | SAST scanner (parallel) |
| SAST | rt-sast-scan | nova2-sast | Nova 2 Lite | SAST scanner (parallel) |
| SAST | rt-sast-scan | hierarchy-analyzer | Sonnet 4.6 | Auth pattern comparison |
| SAST | rt-sast-scan | consolidator | Sonnet 4.6 | 2/3 voting merge |
| SAST | rt-sast-scan | validator | Sonnet 4.6 | Adversarial challenge |
| DAST | rt-scan-idor | gptoss-idor | GPT OSS | DAST IDOR tester (parallel) |
| DAST | rt-scan-idor | sonnet-idor | Sonnet 4.6 | DAST IDOR tester (parallel) |
| DAST | rt-scan-idor | nova2-idor | Nova 2 Lite | DAST IDOR tester (parallel) |
| Pentest | pentest-assessment | pentest-recon | Haiku 4.5 | Port scan + HTTP probe |
| Pentest | pentest-assessment | pentest-vuln-scanner | Haiku 4.5 | Nuclei scans |
| Pentest | pentest-assessment | pentest-exploit-tester | Haiku 4.5 | Validate findings |
| Pentest | pentest-assessment | pentest-report-writer | Haiku 4.5 | Aggregate + report |

## Actor Profiles (Step 8)

| Stage | Context | Goal |
|-------|---------|------|
| recon | Security engineer performing recon on an internal AWS service | Discover all endpoints, accounts, and code packages |
| artifacts | Security reviewer analyzing CDK/CloudFormation code | Find hardcoded secrets, overpermissive IAM, misconfigs |
| sandbox | DevOps engineer deploying infrastructure to a test sandbox | Deploy CFN template and validate all resources |
| sast | SAST analyst scanning source code for IDOR vulnerabilities | Find missing ownership checks, unvalidated resource IDs |
| dast | Pentester testing a REST API for IDOR via cross-tenant requests | Prove IDOR by accessing another user's resources via HTTP |
| pentest | Penetration tester running automated scans | Discover and validate all exploitable vulnerabilities |

## MCP Tool Calls (Step by Step)

### Step 1: SOP Plan
```python
call_brick_tool(brick_name="evals", tool_name="evals_sop_plan",
    arguments='{"agent_description": "<FULL system prompt + role + tools + graph position>",
                "agent_tools": ["<actual tool list from registry>"],
                "evaluation_goals": "<what matters for this agent>"}')
# Returns: session_id, recommended_evaluators, test_categories, success_criteria
```

### Step 2: Generate Test Data
```python
call_brick_tool(brick_name="evals", tool_name="evals_sop_generate_data",
    arguments='{"session_id": "<from step 1>", "num_cases": 8}')
# Returns: test cases with inputs and expected outputs
```

### Step 3: Run Eval
```python
call_brick_tool(brick_name="evals", tool_name="evals_sop_run",
    arguments='{"session_id": "<same>",
                "model_id": "<agent actual model>",
                "system_prompt": "<agent actual system prompt>",
                "evaluator_names": ["<from step 1 recommendations>"]}')
# Returns: per-case scores with judge reasoning
```

### Step 4: Report
```python
call_brick_tool(brick_name="evals", tool_name="evals_sop_report",
    arguments='{"session_id": "<same>"}')
# Returns: failure patterns, improvement recommendations
```

### Step 5: Improve (manual — apply recommendations)

### Step 6: Re-run SOP (repeat Steps 1-4 on improved agent, compare scores)

### Step 7: Experiment
```python
call_brick_tool(brick_name="evals", tool_name="evals_generate_experiment",
    arguments='{"context": "<agent context>", "task_description": "<goals>", "num_cases": 5}')
# Then:
call_brick_tool(brick_name="evals", tool_name="evals_run_experiment",
    arguments='{"cases": <from above>, "model_id": "<agent model>",
                "system_prompt": "<agent prompt>", "experiment_name": "exp-<agent_id>"}')
```

### Step 8: Simulation
```python
call_brick_tool(brick_name="evals", tool_name="evals_run_simulation",
    arguments='{"cases": [{"name": "sim-<agent_id>",
                           "input": "<actor goal>",
                           "metadata": {"task_description": "<actor goal>"}}],
                "model_id": "<agent model>",
                "system_prompt": "<agent prompt>",
                "max_turns": 5, "experiment_name": "sim-<agent_id>",
                "persist": true}')
```

With `persist=true`, retain the returned `run_id` and `record_run_request`. If
persistence needs a retry, call `evals_run_simulation` with `persist_only=true`,
the same `run_id`, and that exact request; do not rerun the model invocation.

### Optional: Tool-chaos resilience check

Use `evals_run_tool_chaos` only for a prompt-only target and a bounded subset of
the developer-owned catalog. It creates paired baseline/fault evidence through
native Strands ToolSimulator and ChaosExperiment APIs; caller-supplied tool
callables/schemas and registered-persona `agent_id` targets are rejected.

```python
call_brick_tool(brick_name="evals", tool_name="evals_run_tool_chaos",
    arguments='{"cases": [{"input": "Find the account status"}],
                "tool_names": ["account_lookup"],
                "faults": [{"condition": "lookup-timeout",
                  "tool_effects": {"account_lookup": [
                    {"effect_type": "timeout", "error_message": "timeout"}]}}]}')
```

Red-team and multimodal execution are not an alternative path here; they remain
blocked pending the required authorization, sandbox, redaction, retention,
audit, and kill-switch infrastructure.

## Output Structure

Terminal evaluation evidence is durably stored through the Evals → Storage MCP
path. Full runs use immutable `eval-{run_id}` documents; P/R/F1 projections use
isolated `eval-score-{run_id}` documents. Equal retry payloads match, divergent
ones conflict without mutation, and Graph/events receive only a post-commit
pointer plus scalar summary. Full per-agent JSON may also be written to
`projects/the control-plane project/challenges/experiments/agents/<agent_id>.json`.

### Report Structure (capture EVERYTHING from MCP tool responses)

```json
{
  "agent_eval_version": "2.0.0",
  "generated_at": "...",
  "iteration": 1,
  "input": {
    "agent_id": "...", "workflow": "...", "stage": "...",
    "model": "...",
    "system_prompt": "FULL actual system prompt from registry",
    "tools": [], "eval_goals": "..."
  },
  "step1_plan": {
    "session_id": "...",
    "recommended_evaluators": [],
    "test_categories": [],
    "success_criteria": {}
  },
  "step2_test_data": {
    "case_count": 8,
    "cases": [
      {"id": "...", "name": "...", "input": "FULL input", "expected_output": "FULL expected"}
    ]
  },
  "step3_eval": {
    "overall_score": 0.0, "pass_rate": 0.0,
    "case_results": [
      {"name": "...", "score": 0.0, "passed": true,
       "reason": "FULL judge reasoning — the WHY"}
    ]
  },
  "step4_report": {
    "failure_patterns": [],
    "improvement_recommendations": []
  },
  "step5_improvements": {
    "changes_made": ["what changed and why"],
    "before_prompt": "...", "after_prompt": "...",
    "model_swapped": false
  },
  "step6_rerun": {
    "overall_score": 0.0, "pass_rate": 0.0,
    "delta_from_step3": "+X.X%",
    "case_results": [...]
  },
  "step7_experiment": {
    "overall_score": 0.0, "pass_rate": 0.0,
    "case_results": [
      {"name": "...", "score": 0.0, "reason": "FULL judge reasoning"}
    ]
  },
  "step8_simulation": {
    "actor_profile": {"context": "...", "goal": "..."},
    "simulation_input": "FULL prompt",
    "overall_score": 0.0,
    "case_results": [
      {"name": "...", "score": 0.0, "reason": "FULL judge reasoning"}
    ]
  },
  "summary": {
    "initial_sop_score": 0.0,
    "post_improvement_score": 0.0,
    "experiment_score": 0.0,
    "simulation_score": 0.0,
    "improvement_delta": "+X.X%",
    "verdict": "...",
    "thought": "1-2 sentence hot take"
  }
}
```

### Key rule: NEVER summarize MCP tool responses — copy them verbatim

- Step 2 cases: Full input + expected output for every test case
- Step 3/6/7 case_results.reason: FULL judge reasoning string — this is the WHY
- Step 4 recommendations: FULL text from the SOP report
- Step 5 changes: Exact before/after of what was modified
- Step 8 simulation_input: Exact prompt sent to ActorSimulator
- summary.thought: Human-readable hot take for the team

## V1 Archive

First-pass reports (snapshot without iteration loop) archived at:
`projects/the control-plane project/challenges/experiments/agents/archive-v1/`

These used a 6-phase approach (SOP + Experiment + Simulation without the improve/re-run loop).
Key findings from V1 that inform V2 iteration targets:
- Nova 2 Lite: unusable (max_tokens + content filters) — swap candidate
- Validator (Sonnet): too adversarial (20% score) — model swap candidate
- GPT OSS: great at SAST, terrible at DAST — role reassignment candidate
- Haiku: excellent at reporting, refuses pentest recon — prompt fix candidate

## Best Practices (from team research)

| # | Practice | Source | How It Applies |
|---|----------|--------|----------------|
| 1 | Ensemble Diversity | Chen et al. 2026 | Different models per scanner role |
| 2 | Disagreement Resolution | arXiv:2502.19130 | 2/3 voting in consolidator |
| 3 | Execution Grounding | Co-RedTeam, MAPTA | Agents must cite sources from file_read |
| 4 | Graph RAG at Decision Time | Lewis et al. 2020 | Graph stores facts for cross-agent access |
| 5 | Confidence Calibration | arXiv:2503.02623 | Deterministic confidence scoring |
| 6 | Structured Reflection | Huang et al. 2022 | Generate → Critique → Refine per agent |
| 7 | Tree Search Planning | LATS (ICML 2024) | Attack mapping before agent work |
| 8 | Adversarial Self-Validation | D3, Applied Sciences 2025 | Agent argues against own reasoning |
| 9 | Eval Feedback Loop | Co-RedTeam, TermiAgent | Evals integrated into workflow |
| 10 | GT Expansion | arXiv:2511.10049 | Agents process new scenarios from GT DB |

## MCP Tools Used

| Tool | Step | Purpose |
|------|------|---------|
| `evals_sop_plan` | 1 | Create eval plan from agent code/config |
| `evals_sop_generate_data` | 2 | Auto-generate test cases |
| `evals_sop_run` | 3, 6 | Run agent against cases with evaluators |
| `evals_sop_report` | 4 | Produce failure patterns + recommendations |
| `evals_generate_experiment` | 7 | Generate independent test cases |
| `evals_run_experiment` | 7 | Run experiment with generated cases |
| `evals_run_simulation` | 8 | Multi-turn ActorSimulator conversation; returns a retry request when persisted |
| `evals_run_tool_chaos` | Optional | Paired native ToolSimulator baseline/fault evaluation over an allowlisted catalog |
| `evals_record_run` | — | Create or match an immutable terminal record through Storage MCP |
| `evals_sop_list` | — | List all SOP sessions (UI) |
| `evals_list_runs` | — | List suite-run state (UI) |
