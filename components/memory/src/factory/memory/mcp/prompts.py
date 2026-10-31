"""MCP prompts for memory brick."""

from __future__ import annotations

from typing import Any

from factory.memory.runtime.runtime import MemoryRuntime


def register(mcp: Any, runtime: MemoryRuntime) -> None:
    """Register MCP prompts."""

    @mcp.prompt()
    def configure_memory() -> str:
        """Guide for configuring memory backend."""
        return """# Configure Memory Backend

## Step 1: Choose a backend
Available backends:
- `memory` - In-memory (default, for testing)
- `mem0` - Mem0.ai semantic memory
- `agentcore` - AWS Bedrock AgentCore Memory
- `zep` - Zep long-term memory with temporal awareness
- `cognee` - Cognee knowledge-graph-enriched memory

## Step 2: Set configuration
```python
from factory.memory.runtime.models import Settings
from factory.memory.runtime.runtime import MemoryRuntime

settings = Settings(
    backend="mem0",
    default_ttl_seconds=3600,  # 1 hour
    max_memories_per_user=1000,
)
runtime = MemoryRuntime(settings=settings)
```

## Step 3: For Mem0 backend
```bash
pip install mem0ai
export MEM0_API_KEY=your_key
```

## Step 4: For AgentCore backend
```bash
pip install 'bedrock-agentcore[strands-agents]'
# Configure AWS credentials
```

## Step 5: For Zep backend
```bash
pip install zep-python
export ZEP_API_KEY=your_key
```

## Step 6: For Cognee backend
```bash
pip install cognee
# Configure cognee settings
```

## Step 7: Verify
Use `health_check()` to verify the backend is working.
"""

    @mcp.prompt()
    def debug_memory() -> str:
        """Guide for debugging memory issues."""
        current = runtime.settings
        health = runtime.health_check()
        stats = runtime.stats()

        return f"""# Debug Memory Issues

## Current State
- Backend: {current.backend}
- Health: {"✅ Healthy" if health.healthy else "❌ Unhealthy"}
- Total memories: {stats.total_memories}
- By type: {stats.by_type}

## Common Issues

### Low relevance scores
- Check min_relevance threshold (default 0.3)
- For in-memory backend, uses simple text similarity
- Consider Mem0 for better semantic matching

### Memories not persisting
- In-memory backend is volatile (lost on restart)
- Use Zep, Cognee, or Mem0 for persistence

### Memory not found
- Check if TTL expired
- Verify user_id matches

## Diagnostic Tools
1. `memory_stats()` - Get statistics
2. `memory_list(user_id)` - List all user memories
3. `health_check()` - Check backend health
"""

    @mcp.prompt()
    def optimize_retrieval() -> str:
        """Guide for optimizing memory retrieval."""
        return """# Optimize Memory Retrieval

## Relevance Tuning
- Lower `min_relevance` (0.1-0.3) for broader matches
- Higher `min_relevance` (0.7-0.9) for precise matches

## Memory Organization
- Use categories to filter: preference, fact, summary, context
- Use memory_type to scope: short_term, long_term, episodic

## Backend Selection
| Use Case | Recommended Backend |
|----------|-------------------|
| Testing | memory |
| Semantic search | mem0 |
| AWS integration | agentcore |
| Companion/conversational | zep |
| Knowledge-graph reasoning | cognee |

## Consolidation Strategy
- Call `memory_consolidate(user_id)` periodically
- Moves short_term → long_term
- Reduces noise in retrieval

## Query Tips
- Be specific in queries for better relevance
- Use natural language that matches stored content
- Combine with category filters for precision
"""
