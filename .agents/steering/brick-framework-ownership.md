---
inclusion: manual
---
# Brick Framework Ownership

Frameworks live in the brick whose domain they serve and are exposed only
through that brick's MCP surface and public `interface.py`.

## Principle — frameworks live in the brick they serve

A *framework* is an upstream SDK, library, or algorithm that solves a domain
problem. It is owned by the brick whose domain it serves and hidden behind that
brick's `runtime/ports.py` Protocols and `runtime/adapters/` implementations.
Other bricks discover the capability through MCP tools and `factory.<brick>.interface`.

- Framework code is imported only inside the owning brick's adapters.
- Public contracts are typed Pydantic models in `runtime/models.py`.
- Exposure is through `interface.py` and the brick's MCP tools/resources/prompts.

## Canonical examples

| Framework(s) | Owning brick | Notes |
|---|---|---|
| AgentInstruct, S2M, APIGenMT, ReviewInstruct | `dataset` | Internal `DatasetStagePort` adapters only. |
| Strands / Bedrock agent runtime | `agent` | Skills and playbooks are behavioral guidance. |
| MLX, AI-Fine-Tuning, MLflow, Weights & Biases | `machine_learning` | Fine-tuning and experiment tracking live here. |
| Provider routing | `llm_gateway` | All LLM calls route through this surface. |

## Cross-brick composition rules

- Need a capability from another domain? Call that brick's MCP tools or use
  `factory.<other>.interface`. Never import another brick's runtime internals.
- Shared contracts are typed Pydantic models and immutable artifact references
  (URI + digest + manifest).
- Direct internal imports across `components/` are prohibited.
- Never route LLM calls through `agent` when `llm_gateway` exists.

## Anti-patterns

- Parking a framework in a shared/util brick because multiple domains touch it.
- Letting one brick execute another brick's domain stages directly.
- Using agent skills, swarm, or graph to run dataset stages instead of calling
  `dataset_submit_generation`.
- Writing recipes directly to storage from the agent instead of via a `dataset`
  MCP tool.

## Decision checklist

Before adding a new framework or adapter, answer:

1. Which brick's domain does the framework primarily serve?
2. Can it be hidden behind a port in `runtime/ports.py`?
3. Which MCP tools and public interface expose it?
4. If the owning brick is ambiguous, open a meta-architect review bead.

## References

- `.github/spec/ml-dataset-generation.md` — dataset/agent/ML/llm_gateway boundary
- `.agents/steering/dev-principles.md` — MCP-First, SDK-First, No Cross-Imports
- `.agents/steering/brick-anatomy.md` — ports, adapters, and MCP primitives
