"""Documentation content for llm_gateway MCP resources."""

LLM_DOCS = {
    "overview": {
        "title": "LLM Gateway Overview",
        "content": """# LLM Gateway Brick

Unified interface for LLM completions and embeddings across multiple providers.

## Core Concepts

- **LLMProvider**: Protocol for text/chat completions
- **EmbeddingProvider**: Protocol for vector embeddings
- **Adapters**: Pluggable backends (Bedrock, OpenAI, Anthropic)
- **Runtime**: Factory for creating provider instances

## Quick Start

1. Text completion:
```
llm_complete(prompt="What is 2+2?", backend="bedrock")
```

2. Chat completion:
```
llm_chat(
    messages=[
        {"role": "system", "content": "You are helpful."},
        {"role": "user", "content": "Hello!"}
    ],
    backend="openai"
)
```

3. Embeddings:
```
llm_embed(texts=["Hello world"], backend="bedrock")
```

## Backends

- `bedrock` - AWS Bedrock (Claude, Titan)
- `openai` - OpenAI API (GPT-4, text-embedding)
- `anthropic` - Anthropic API (Claude)

## MCP Tools

- `llm_complete` - Text completion
- `llm_chat` - Chat completion
- `llm_embed` - Generate embeddings
- `llm_list_backends` - List available backends
""",
    },
    "adapters": {
        "title": "LLM Adapter Documentation",
        "content": """# LLM Adapters

The llm_gateway brick uses a ports-and-adapters architecture.

## Bedrock Adapter

AWS Bedrock for Claude and Titan models.

**Features:**
- Claude models (Sonnet 4.5, Haiku 4.5)
- Titan embeddings
- AWS IAM authentication
- Regional deployment

**Configuration:**
```python
provider = runtime.get_provider("bedrock", region="us-east-1")
```

## OpenAI Adapter

OpenAI API for GPT models.

**Features:**
- GPT-4, GPT-3.5 models
- text-embedding-3 models
- API key authentication

**Configuration:**
```python
provider = runtime.get_provider("openai", api_key="sk-...")
```

## Anthropic Adapter

Anthropic API for Claude models.

**Features:**
- Claude models
- API key authentication
- Direct API access

**Configuration:**
```python
provider = runtime.get_provider("anthropic", api_key="sk-ant-...")
```

## Implementing Custom Adapters

Implement the `LLMProvider` protocol:

```python
class MyProvider:
    def complete(self, prompt, model, max_tokens, temperature, **kwargs): ...
    def chat(self, messages, model, max_tokens, temperature, **kwargs): ...
    async def complete_async(self, prompt, model, max_tokens, temp, **kw): ...
    async def chat_async(self, messages, model, max_tokens, temp, **kw): ...
    def health_check(self) -> LLMHealth: ...
```
""",
    },
    "models": {
        "title": "Model Reference",
        "content": """# Model Reference

## Bedrock Models

| Model | ID | Use Case |
|-------|-----|----------|
| Claude Sonnet 4.5 | anthropic.claude-sonnet-4-5-* | General purpose |
| Claude Haiku 4.5 | anthropic.claude-haiku-4-5-* | Fast, cost-effective |
| Titan Embed | amazon.titan-embed-text-v1 | Embeddings |

## OpenAI Models

| Model | ID | Use Case |
|-------|-----|----------|
| GPT-4 Turbo | gpt-4-turbo | Best quality |
| GPT-4o | gpt-4o | Multimodal |
| GPT-3.5 Turbo | gpt-3.5-turbo | Fast, cheap |
| Embedding v3 | text-embedding-3-small | Embeddings |

## Anthropic Models

| Model | ID | Use Case |
|-------|-----|----------|
| Claude Opus 4.5 | claude-opus-4-5-* | Highest quality |
| Claude Sonnet 4.5 | claude-sonnet-4-5-* | Balanced |
| Claude Haiku 4.5 | claude-haiku-4-5-* | Fast |
""",
    },
}
