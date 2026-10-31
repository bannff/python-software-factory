# Recipe: Agent Loop

Validates the core agent execution cycle with LLM, memory, and observability.

## Bricks Used
- `agent` - Agent orchestration
- `llm_gateway` - LLM completions
- `memory` - Agent memory
- `telemetry` - Distributed tracing

## Scenario

An agent receives a task, calls an LLM to reason, stores context in memory, and traces the execution.

## Prerequisites

- AWS credentials available (for Bedrock completions)
- Bricks instantiated with memory adapters

## Steps

### Step 1: Initialize Bricks

```python
import tempfile
from pathlib import Path
import yaml

# Agent - returns tuple of (AgentRuntime, SwarmRuntime, GraphRuntime)
from factory.agent.runtime.runtime import get_default_runtime
agent_runtime, swarm_runtime, graph_runtime = get_default_runtime()

# LLM Gateway (requires AWS)
from factory.llm_gateway.runtime.runtime import LLMRuntime
llm_runtime = LLMRuntime()
llm_provider = llm_runtime.get_provider("bedrock", region_name="us-east-1")

# Memory
from factory.memory.runtime.runtime import MemoryRuntime
memory = MemoryRuntime()

# Telemetry
tmpdir_tel = Path(tempfile.mkdtemp())
(tmpdir_tel / "exporters").mkdir(parents=True, exist_ok=True)
(tmpdir_tel / "metrics").mkdir(parents=True, exist_ok=True)
(tmpdir_tel / "settings.yaml").write_text(yaml.safe_dump({
    "schema_version": 1,
    "service": {"name": "recipe-agent-loop", "version": "1.0.0"},
    "otel": {
        "enabled": True,
        "tracing_enabled": True,
        "metrics_enabled": True,
        "logging_enabled": False,
    },
}))

from factory.telemetry.runtime.runtime import TelemetryRuntime
telemetry = TelemetryRuntime(config_dir=tmpdir_tel)
telemetry.initialize()
```

### Step 2: Health Checks

```python
# LLM provider health
health = llm_provider.health_check()
# Returns: LLMHealth(healthy=True, provider="bedrock", ...)

# Memory health
health = memory.health_check()
# Returns: MemoryHealth(healthy=True, backend="memory", ...)

# Telemetry health
health = telemetry.health_check()
# Returns: {"ok": True, "service": {...}, "otel": {...}}
```

### Step 3: Start Telemetry Span

```python
result = telemetry.start_span(
    name="agent-task",
    attributes={"task": "summarize", "recipe": "agent-loop"},
)
span_id = result.get("span_id")
```

### Step 4: Call LLM (Requires AWS)

```python
# Note: LLMResponse has 'content' not 'text'
response = llm_provider.complete(
    prompt="Summarize the key features of a Polylith architecture.",
    max_tokens=100,
)
completion_text = response.content  # not response.text

# Record LLM interaction in telemetry
telemetry.record_llm_interaction(
    model=response.model,
    input_tokens=response.usage.get("input_tokens", 0),
    output_tokens=response.usage.get("output_tokens", 0),
    latency_ms=None,
    cost_usd=None,
    agent_id="recipe-agent",
    workflow_id="agent-loop",
    trace_attributes={"task": "summarize"},
)
```

### Step 5: Store Result in Memory

```python
from factory.memory.core import MemoryCategory

mem = memory.store(
    user_id="agent-user",
    content=f"Summarized Polylith: {completion_text}",
    memory_type="short_term",
    category=MemoryCategory.SUMMARY,  # enum, not string
    metadata={"type": "task_result", "task": "summarize"},
)
```

### Step 6: Record Agent Execution

```python
telemetry.record_agent_execution(
    agent_id="recipe-agent",
    workflow_id="agent-loop",
    success=True,
    latency_ms=150.0,
    trace_attributes={"task": "summarize"},
)
```

### Step 7: End Telemetry Span

```python
telemetry.end_span(span_id=span_id, error=None)
```

## Success Criteria

- [x] All bricks initialize
- [x] Telemetry span created and closed
- [x] Memory store works
- [x] (If AWS) LLM completion generated
- [x] Telemetry metrics recorded

## API Reference

| Brick | Import | Key Methods |
|-------|--------|-------------|
| agent | `factory.agent.runtime.runtime.get_default_runtime` | Returns tuple |
| agent | `factory.agent.runtime.adapters.strands_mcp_graph.create_mcp_client` | Creates a Strands `MCPClient` over in-memory transport for swarm agents |
| llm_gateway | `factory.llm_gateway.runtime.runtime.LLMRuntime` | `get_provider()` |
| memory | `factory.memory.runtime.runtime.MemoryRuntime` | `store()`, `retrieve()` |
| memory | `factory.memory.core.MemoryCategory` | Enum values |
| telemetry | `factory.telemetry.runtime.runtime.TelemetryRuntime` | `start_span()`, `end_span()` |

## Swarm Tool Access

Swarm agents automatically receive `call_mcp_tool` — no manual tool spec required.

```python
# SwarmExecutor injects call_mcp_tool into every agent automatically.
# Swarm configs use empty tools lists:
swarm_config = {
    "id": "my-swarm",
    "entry_point": "agent-a",
    "agents": [
        {
            "id": "agent-a",
            "model": "us.amazon.nova-lite-v1:0",
            "system_prompt": "Use call_mcp_tool to query the graph.",
            "tools": [],  # call_mcp_tool is injected automatically
        }
    ],
}

# Inside the agent's prompt, reference tools by exact name:
# call_mcp_tool(tool_name='graph_find_entities', arguments='{"limit": 5}')
# call_mcp_tool(tool_name='sandbox.provision', arguments='{}')   # dot-notation also works
# call_mcp_tool(tool_name='sandbox.execute', arguments='{"env_id": "...", "command": "ls"}')
```

`build_mcp_tool()` resolves the invoker from `mcp_utils` service registry first, then falls back to the aggregator directly. Returns `None` if neither is available (agent still runs, just without MCP tool access).
