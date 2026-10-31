# Recipes

Integration playbooks for validating brick combinations. Each recipe is executed by an agent, not as a script.

## How Recipes Work

1. Agent reads the recipe markdown
2. Agent instantiates bricks with appropriate adapters
3. Agent executes the scenario via MCP tools
4. Agent reports results (in chat or GitHub issue)

## Running Recipes

Ask an agent: "Run the auth-flow recipe" or "Test the knowledge-pipeline recipe"

## AWS Setup (for LLM-powered recipes)

Some recipes require AWS Bedrock for LLM calls. To enable:

### 1. Authenticate to AWS

```bash
# Using the org credential helper
aws sts assume-role --role-arn <YOUR_ROLE_ARN> --role-session-name <SESSION>   # or your provider's SSO login

# Or using AWS SSO
aws sso login --profile <PROFILE_NAME>

# Or set credentials directly
export AWS_ACCESS_KEY_ID=...
export AWS_SECRET_ACCESS_KEY=...
```

### 2. Verify Bedrock access

```bash
aws bedrock list-foundation-models --region us-east-1 --query 'modelSummaries[?contains(modelId, `claude`)].modelId'
```

## Recipe Categories

### Core Infrastructure
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `auth-flow.md` | auth, permissions, cache | No |
| `data-layer.md` | storage, cache, graph | No |
| `config-management.md` | config, cache, logger | No |

### AI & ML
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `knowledge-pipeline.md` | kb, llm_gateway, memory | Yes (embeddings/completions) |
| `agent-loop.md` | agent, llm_gateway, memory, telemetry | Yes (completions) |
| `ml-pipeline.md` | machine_learning, storage, telemetry | No |
| `dataset-generation.md` | machine_learning, storage | No |
| `evals-benchmarking.md` | evals, telemetry | No (custom) / Yes (strands) |

### Application Services
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `api-surface.md` | api, auth, cache, graph, storage | No |
| `event-driven.md` | events, notification, workflow | No |
| `payments-billing.md` | payments, events, logger | No |
| `game-session.md` | games, telemetry, events | No |

### External Integration
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `http-integrations.md` | http, integrations, cache, logger | No |
| `blockchain-ledger.md` | blockchain, events, logger | No |
| `sandbox-execution.md` | sandbox, logger, events | No |

### Security & Operations
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `security-ops.md` | security, permissions, auth, logger | No |
| `hardware-simulation.md` | hardware, telemetry | No |

### Substrate & Platform
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `domain-agnostic-substrate.md` | agent, graph, games, memory | No |

### Infrastructure as Code
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `cdk-generation.md` | blueprint (+ AWS adapter specs from any brick) | No (generates files only) |

### UI Flow Recipes (the control-plane runtime Dashboard)
| Recipe | Bricks | Requires AWS |
|--------|--------|------------|
| `ui-metrics-flow.md` | metrics | No |
| `ui-evals-flow.md` | evals | No |
| `ui-ml-flow.md` | machine_learning | No |
| `ui-graph-flow.md` | graph | No (Neo4j required) |
| `ui-findings-flow.md` | security (via AG-UI toolCalls) | No |
| `ui-timeline-flow.md` | agent (via AG-UI state) | No |
| `ui-timeline-correlation-flow.md` | api, agent, mcp_server, mcp_utils | No |

## Brick Coverage

All MCP-enabled bricks are covered by at least one recipe:

| Brick | Recipes |
|-------|--------|
| agent | agent-loop, ui-timeline-flow |
| auth | auth-flow, security-ops, api-surface |
| blockchain | blockchain-ledger |
| cache | auth-flow, data-layer, config-management, http-integrations, api-surface |
| config | config-management |
| evals | evals-benchmarking, ui-evals-flow |
| events | event-driven, game-session, payments-billing, blockchain-ledger, sandbox-execution |
| games | game-session |
| graph | data-layer, api-surface, ui-graph-flow |
| hardware | hardware-simulation |
| http | http-integrations |
| integrations | http-integrations |
| kb | knowledge-pipeline |
| llm_gateway | knowledge-pipeline, agent-loop |
| logger | security-ops, config-management, http-integrations, payments-billing, blockchain-ledger, sandbox-execution |
| machine_learning | ml-pipeline, dataset-generation, ui-ml-flow |
| memory | knowledge-pipeline, agent-loop |
| metrics | metrics-monitoring, ui-metrics-flow |
| notification | event-driven |
| payments | payments-billing |
| permissions | auth-flow, security-ops |
| sandbox | sandbox-execution |
| security | security-ops, ui-findings-flow |
| storage | data-layer, ml-pipeline, dataset-generation, api-surface |
| telemetry | agent-loop, game-session, ml-pipeline, hardware-simulation, evals-benchmarking |
| workflow | event-driven |
| blueprint | cdk-generation |

## Graceful Degradation

Recipes that need AWS will:
- Check for credentials at start
- Skip LLM steps if unavailable
- Report what was tested vs skipped
