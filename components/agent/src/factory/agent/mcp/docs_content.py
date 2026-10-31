"""Documentation content for the Agent brick's MCP resources."""

AGENT_OVERVIEW = """
# Agent Brick

The Agent brick owns bounded intelligent execution. It provides the unified
persona registry, scoped models and MCP capabilities, structured outputs,
LangChain agents, and attempt-local LangGraph execution.

Companion-X assembles bounded objective teams through these surfaces; it is not
a second agent runtime. Workflow durably governs cross-brick attempts, budgets,
retries, cancellation, recovery, and stopping. See the normative doctrine in
`.kiro/steering/python-factory.md`.

## Runtime Primitives

- **Agent** — a registered persona with a scoped model, prompt, and capabilities
- **Graph** — bounded LangGraph research, synthesis, or revision within one attempt
- **Capability client** — the allowlisted native MCP v2 path to brick tools
- **Catalog** — registered personas and bounded graph definitions
"""

LANG_RUNTIME_INTEGRATION = """
# LangChain and LangGraph Integration

The Agent brick uses LangChain for registered agent execution and LangGraph for
explicit, bounded graph workflows. Both receive only capability descriptors and
results from the shared scoped native MCP v2 client; neither opens a second MCP
transport or imports another brick's runtime.

LangGraph state is attempt-local. Workflow remains the sole durable owner of
attempt IDs, budgets, retries, cancellation, recovery, history, and terminal
reasons.
"""

POLYMORPHIC_DESIGN = """
# Agent Runtime Boundary

Registry data defines personas, models, capability scopes, structured output
contracts, and bounded graph definitions. Runtime adapters translate those
neutral contracts into private LangChain or LangGraph types. The MCP layer
exposes stable Agent capabilities without leaking framework objects.

Domain expertise is data. A new domain registers personas and capabilities and
uses the same Agent → Workflow → scoped native MCP v2 → Evals path. Domain-
specific computational work may use registered brick adapters selected through
typed references; it must not create a parallel runtime or domain branch.
"""

GRAPH_PATTERNS = """
# Bounded Graph Patterns

Use LangGraph when one attempt needs explicit stages, evidence handoffs,
structured synthesis, or revision. Bound nodes, transitions, tool scope, time,
and state size.

## Durable Boundary

Workflow owns attempt history, global budgets, retries, cancellation, recovery,
stopping, and terminal reasons. Agent-owned LangGraph execution is private and
bounded to one Workflow attempt.
"""
