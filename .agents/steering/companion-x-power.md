---
inclusion: auto
---

# the control-plane runtime Power — Canonical Usage for Sub-Agents

All sub-agents (implementer, meta-architect, qa-tester, doc-writer, security-engineer,
strands-expert, ux-designer) MUST use the **`the control-plane runtime` Kiro power** to interact
with the running the control-plane runtime MCP server. Do not use raw HTTP, `urllib`, `curl`,
or fabricated `call_brick_tool(...)` pseudo-syntax. Those approaches do not log
to the company memory store and break the consultation audit trail.

This file is auto-included for ALL agents. The canonical invocation pattern below
is the only supported way to call the control-plane runtime bricks from a sub-agent.

## Canonical Invocation

```python
kiroPowers(
  action="use",
  powerName="the control-plane runtime",
  serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={
    "brick_name": "<brick>",          # e.g. "memory", "graph", "kb"
    "tool_name":  "<tool>",            # e.g. "memory_store"
    "arguments":  "<json-string>",     # JSON-stringified payload
  },
)
```

Note: `arguments` is itself a JSON-encoded string. Do not pass a dict.

`serverName` equals `powerName` for `the control-plane runtime` (the power exposes one MCP
server with the same name). Some powers expose multiple servers — for those,
look up the right `serverName` via `kiroPowers(action="activate", powerName=...)`
and read the `toolsByServer` map.

## Memory Store (consultation logging — MANDATORY)

Every consult MUST be logged via this exact pattern. The the control-plane runtime memory brick
backs the audit trail; entries logged via other channels will not surface in
`memory_retrieve` queries by the audit hooks.

```python
kiroPowers(
  action="use",
  powerName="the control-plane runtime",
  serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={
    "brick_name": "memory",
    "tool_name":  "memory_store",
    "arguments": json.dumps({
      
      "content": "[CONSULT bd:<id> phase:<phase> specialist:<name>] <verdict>: ...",
      "category": "fact",
      "metadata": {
        "bd_id":      "<id>",
        "specialist": "<name>",
        "phase":      "<phase>",
        "verdict":    "<verdict>",
        "files_reviewed": "<comma-separated>",
      },
    }),
  },
)
```

The `content` field MUST start with `[CONSULT bd:<id>` so the audit hook can
locate it deterministically.

## Memory Retrieve (consultation lookup)

```python
kiroPowers(
  action="use",
  powerName="the control-plane runtime",
  serverName="the control-plane runtime",
  toolName="call_brick_tool",
  arguments={
    "brick_name": "memory",
    "tool_name":  "memory_retrieve",
    "arguments": json.dumps({
      
      "query":   "[CONSULT bd:<id>",
      "limit":   20,
    }),
  },
)
```

## Progressive Discovery

```python
# List all bricks (tools_count: -1 means lazy-loaded)
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
           toolName="list_bricks", arguments={})

# Trigger lazy-load + get tool schemas
kiroPowers(action="use", powerName="the control-plane runtime", serverName="the control-plane runtime",
           toolName="get_brick_tools", arguments={"brick_name": "memory"})
```

## What NOT To Do

- ❌ `call_brick_tool(brick_name="memory", ...)` — pseudo-syntax, doesn't actually invoke anything
- ❌ `curl http://localhost:8000/...` — bypasses the power, no audit trail
- ❌ `urllib.request.Request(...)` — same problem
- ❌ Inline Python that imports `factory.memory.interface` directly — sub-agents cannot import bricks

## When the Power Is Unreachable

If `kiroPowers(action="use", powerName="the control-plane runtime", ...)` fails (the control-plane runtime server
down, Dolt offline, AWS creds stale), state so plainly in the verdict and skip
the memory write. Do NOT fabricate the entry or use a fallback channel that will
not surface in audit retrievals.
