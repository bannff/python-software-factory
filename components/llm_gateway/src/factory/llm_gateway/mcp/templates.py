"""Prompt templates for llm_gateway MCP prompts."""

PROMPT_TEMPLATES = {
    "configure_backend": {
        "description": "Guide for setting up LLM backend",
        "template": """# Configure LLM Backend: {backend}

## Current Configuration
{current_config}

## Setup Guide
{setup_guide}

## Configuration Options

```python
from factory.llm_gateway.runtime.runtime import LLMRuntime

runtime = LLMRuntime()
provider = runtime.get_provider("{backend}"{config_params})
```

## Verification Steps

1. Check health:
```
health_check()
```

2. Test completion:
```
llm_complete(prompt="Hello!", backend="{backend}")
```

3. Test chat:
```
llm_chat(
    messages=[{{"role": "user", "content": "Hi"}}],
    backend="{backend}"
)
```
""",
    },
    "debug_llm": {
        "description": "Help debugging LLM issues",
        "template": """# Debug LLM Issues

## Issue
{issue}

## Diagnostic Steps

### 1. Check Provider Health
```
health_check()
```

### 2. List Available Backends
```
llm_list_backends()
```

### 3. Test Simple Completion
```
llm_complete(prompt="Say hello", backend="{backend}", max_tokens=10)
```

## Common Issues

| Symptom | Cause | Fix |
|---------|-------|-----|
| Auth error | Invalid credentials | Check API key/IAM |
| Timeout | Model overloaded | Retry or use different model |
| Rate limit | Too many requests | Add backoff/retry |
| Invalid model | Wrong model ID | Check model reference |

## Backend-Specific Debugging

### Bedrock
- Check AWS credentials: `aws sts get-caller-identity`
- Verify model access in Bedrock console

### OpenAI
- Verify API key: Check OpenAI dashboard
- Check rate limits and quotas

### Anthropic
- Verify API key: Check Anthropic console
- Check usage limits
""",
    },
    "optimize_prompts": {
        "description": "Guide for prompt optimization",
        "template": """# Optimize LLM Prompts

## Current Usage
{current_usage}

## Analysis

### Token Usage
{token_analysis}

### Response Quality
{quality_analysis}

## Optimization Recommendations

### 1. Prompt Engineering
- Be specific and clear
- Use examples (few-shot)
- Structure with sections

### 2. Parameter Tuning
| Parameter | Current | Recommended |
|-----------|---------|-------------|
| temperature | {temperature} | {rec_temperature} |
| max_tokens | {max_tokens} | {rec_max_tokens} |

### 3. Model Selection
{model_recommendations}

## Cost Optimization

- Use smaller models for simple tasks
- Cache common responses
- Batch similar requests
""",
    },
}

BACKEND_GUIDES = {
    "bedrock": {
        "setup_guide": """AWS Bedrock requires AWS credentials and model access.

1. Configure AWS credentials:
```bash
aws configure
```

2. Enable model access in Bedrock console:
   - Go to AWS Console > Bedrock > Model access
   - Request access to Claude models

3. Set region (optional):
```bash
export AWS_DEFAULT_REGION=us-east-1
```""",
        "config_params": ', region="us-east-1"',
    },
    "openai": {
        "setup_guide": """OpenAI requires an API key.

1. Get API key from https://platform.openai.com/api-keys

2. Set environment variable:
```bash
export OPENAI_API_KEY=sk-...
```

Or pass directly:
```python
provider = runtime.get_provider("openai", api_key="sk-...")
```""",
        "config_params": ', api_key="sk-..."',
    },
    "anthropic": {
        "setup_guide": """Anthropic requires an API key.

1. Get API key from https://console.anthropic.com/

2. Set environment variable:
```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

Or pass directly:
```python
provider = runtime.get_provider("anthropic", api_key="sk-ant-...")
```""",
        "config_params": ', api_key="sk-ant-..."',
    },
}
