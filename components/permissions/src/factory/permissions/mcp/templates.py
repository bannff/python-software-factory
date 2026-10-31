"""Prompt templates for permissions brick."""

PROMPT_TEMPLATES = {
    "create_policy": {
        "description": "Guide for creating a new access control policy",
        "template": """# Create Policy: {name}

## Purpose
{purpose}

## Policy Definition

Create a file at `config/policies/{id}.yaml`:

```yaml
schema_version: 1
id: {id}
name: {name}
version: "1.0"
tags: [{tags}]
rules:
{rules_yaml}
```

## Validation

After creating, validate with:
```
permissions.authoring.validate_policies()
```

## Test Evaluation

```
permissions.evaluate(
    action="{test_action}",
    resource={{"type": "{resource_type}", "id": "test-123"}}
)
```
""",
    },
    "debug_denial": {
        "description": "Help debugging why a permission was denied",
        "template": """# Debug Permission Denial

## Request Details
- Action: {action}
- Resource Type: {resource_type}
- Resource ID: {resource_id}
- Principal: {principal_id}

## Debugging Steps

### 1. Get Detailed Explanation
```
permissions.explain(
    action="{action}",
    resource={{"type": "{resource_type}", "id": "{resource_id}"}},
    envelope={{"principal_id": "{principal_id}"}}
)
```

### 2. Check Loaded Policies
```
permissions.get_policy_registry()
```

### 3. Check Role Permissions
```
permissions.get_role_registry()
```

### 4. Common Causes
- No matching allow rule
- Explicit deny rule matched
- Missing resource attributes
- Condition not satisfied
- Wrong principal/tenant context
""",
    },
    "audit_review": {
        "description": "Guide for reviewing permission audit logs",
        "template": """# Audit Review

## Query Parameters
- Time Range: {time_range}
- Principal: {principal_id}
- Resource Type: {resource_type}

## Review Steps

1. Check recent denials for patterns
2. Identify frequently accessed resources
3. Review policy matches
4. Look for anomalous access patterns

## Integration

The audit store captures:
- All evaluate() calls
- Decision and reason
- Matched policy/rule
- Full context
""",
    },
}


def get_template(name: str) -> str | None:
    """Get template by name."""
    return PROMPT_TEMPLATES.get(name, {}).get("template")


def list_templates() -> list[str]:
    """List available templates."""
    return list(PROMPT_TEMPLATES.keys())
