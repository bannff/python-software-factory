"""Documentation content for memory brick."""

DOCS: dict[str, str] = {
    "overview": """# Memory Brick

Agent memory abstraction with pluggable backends.

## Features
- Semantic memory retrieval with relevance scoring
- Short-term, long-term, and episodic memory types
- Memory consolidation (STM → LTM)
- TTL support for automatic expiration
- Multiple backend adapters

## Memory Types
- **short_term**: Volatile, session-scoped memories
- **long_term**: Persistent, cross-session memories
- **episodic**: Event-based memories with temporal context

## Categories
- **preference**: User preferences and settings
- **fact**: Factual information about the user
- **summary**: Conversation/session summaries
- **context**: Contextual information
- **custom**: User-defined categories
""",
    "adapters": """# Memory Adapters

## In-Memory (default)
Volatile storage for testing. Uses simple text similarity.

## Mem0
Integration with mem0.ai for semantic memory:
- Vector-based similarity search
- Automatic memory extraction
- Cross-conversation persistence

## AgentCore
AWS Bedrock AgentCore Memory:
- Managed STM/LTM strategies
- Summary, preference, and semantic strategies
- Namespace-based scoping

## Zep
Long-term agent memory with temporal awareness:
- Automatic fact and entity extraction
- Temporal relationship tracking
- Session-scoped and user-scoped memory
- Semantic search over extracted facts

## Cognee
Knowledge-graph-enriched memory:
- Automatic entity and relationship extraction
- Graph-based semantic search
- Cross-document reasoning
- Structured knowledge representation
""",
    "usage": """# Usage Examples

## Store a memory
```python
runtime.store(
    user_id="user123",
    content="User prefers dark mode",
    memory_type="long_term",
    category="preference"
)
```

## Retrieve memories
```python
memories = runtime.retrieve(
    user_id="user123",
    query="What are the user's UI preferences?",
    min_relevance=0.5,
    limit=5
)
```

## Consolidate memories
```python
count = runtime.consolidate(user_id="user123")
```
""",
}
