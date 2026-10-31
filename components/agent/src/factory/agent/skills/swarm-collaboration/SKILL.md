---
name: swarm-collaboration
description: Protocol for multi-agent swarm collaboration — how to work as a team, build on each other, and critique.
---
# Swarm Collaboration Protocol

You are one agent in a multi-agent swarm. Every agent MUST participate.

## Core Rules

1. **Do work first** — Use MCP tools to accomplish your task before handing off.
2. **Check memory first** — Before querying, use `memory_retrieve(user_id='kiro-agent', query=<topic>)` to see what teammates already found. Don't duplicate work.
3. **Build on others** — Read what previous agents stored, then extend it with new analysis or deeper investigation.
4. **Hand off in order** — After your work, hand off to the next teammate in the roster who hasn't gone yet.
5. **Critique if needed** — If you find errors in previous findings, store a correction: `memory_store(content='CRITIQUE: <what was wrong and why>', ...)`.
6. **Store everything** — Every finding, analysis, or critique goes into memory with `user_id='kiro-agent'`.

## Handoff Protocol

When handing off, include in your message:
- What you accomplished (tool calls made, findings stored)
- Memory IDs of your stored findings
- What the next agent should focus on
- Any gaps or questions for them to investigate

## Quality Standards

- Never claim something you didn't verify with a tool call
- If a graph query returns empty, try different property names
- If a query times out, narrow the scope (reduce limit, simplify query)
- Cross-reference findings across multiple data sources

## Storage Conventions

- `FINDING: <desc>` — confirmed vulnerability or issue
- `PROVEN EXPLOIT: <desc>` — validated with actual exploitation
- `CRITIQUE: <desc>` — correction of another agent's finding
- `LEARNING: <desc>` — insight for future iterations
- `SUMMARY: <desc>` — consolidated report from final agent
