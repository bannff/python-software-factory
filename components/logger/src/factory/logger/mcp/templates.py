"""Prompt templates for logger MCP prompts."""

PROMPT_TEMPLATES = {
    "debug_errors": {
        "description": "Help debugging errors in logs",
        "template": """# Debug Errors

## Recent Errors Found
{error_summary}

## Debugging Steps

### 1. Get Full Context
```
logger.search(level="error", limit=20)
```

### 2. Filter by Source
If errors are from a specific brick:
```
logger.search(level="error", source="{source}", limit=20)
```

### 3. Trace a Run
If you have a run_id:
```
logger.search(run_id="{run_id}")
```

### 4. Check Related Bricks
- `workflow.get_run(run_id="...")` - Check workflow status
- `auth.health_check()` - Verify auth is healthy

## Common Error Patterns

- **Connection errors**: Check external service health
- **Validation errors**: Check input data format
- **Permission errors**: Verify auth/permissions config
""",
    },
    "configure_logging": {
        "description": "Guide for configuring logging",
        "template": """# Configure Logging

## Current Configuration
{current_config}

## Configuration Options

### Log Directory
```yaml
logger:
  log_dir: ./logs  # Where logs are stored
```

### Log Format
```yaml
logger:
  format: json  # or "text" for human-readable
```

### Log Level
```yaml
logger:
  level: info  # debug, info, warning, error, critical
```

## Verification

1. Check health: `logger.health_check()`
2. Test logging: `logger.info(message="Test message")`
3. Verify output: `logger.tail(lines=5)`
""",
    },
    "trace_run": {
        "description": "Trace all logs for a specific run",
        "template": """# Trace Run: {run_id}

## All Logs for This Run
{log_entries}

## Analysis Steps

### 1. Timeline View
Logs are ordered chronologically. Look for:
- First error occurrence
- State transitions
- External calls

### 2. Cross-Reference
Check related systems:
```
workflow.get_run(run_id="{run_id}")
```

### 3. Context Clues
Look at the `context` field for:
- Input parameters
- Intermediate values
- External IDs

## Next Steps
{next_steps}
""",
    },
}

SINK_GUIDES = {
    "file": {
        "setup_guide": "No setup required. Logs written to `./logs/factory.log`.",
        "config": """  log_dir: ./logs
  filename: factory.log""",
    },
    "cloudwatch": {
        "setup_guide": """### Prerequisites
- AWS credentials configured
- CloudWatch Logs access

```bash
aws configure
```""",
        "config": """  sink: cloudwatch
  cloudwatch:
    log_group: /factory/logs
    log_stream: main""",
    },
}
