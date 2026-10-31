"""Documentation content for permissions brick."""

PERMISSIONS_OVERVIEW = """
# Permissions Brick

Policy-based access control with YAML-defined rules and audit logging.

## Core Concepts

- **Policy**: Collection of rules that define access control
- **Rule**: Single allow/deny decision with conditions
- **Resource**: Entity being accessed (type, id, owner, attributes)
- **Action**: Operation being performed (read, write, delete, etc.)
- **Envelope**: Request context (principal_id, tenant_id)

## Quick Start

1. Define policies in `config/policies/*.yaml`
2. Evaluate: `permissions.evaluate(action="read", resource={...})`
3. Inspect the `ToolResult` envelope and its typed `data.decision` field.

## MCP Tools

### Deterministic (queries)
- `permissions.get_capabilities` - Feature list and live tool catalog
- `permissions.health_check` - Readiness probe
- `permissions.describe_config_schema` - Settings schema
- `permissions.get_role_registry` - List roles
- `permissions.get_policy_registry` - List policies

### Operational (evaluation)
- `permissions.evaluate` - Single permission check
- `permissions.batch_evaluate` - Multiple checks
- `permissions.explain` - Detailed evaluation trace

### Authoring (config changes; gated and disabled by default)
- `permissions.authoring.get_status` - Authoring gate status
- `permissions.authoring.upsert_policy` - Create/update policy
- `permissions.authoring.delete_policy` - Remove policy
- `permissions.authoring.validate_policies` - Validate all
"""

POLICY_SYNTAX = """
# Policy Syntax

Policies are YAML files defining access control rules.

## Structure

```yaml
schema_version: 1
id: my-policy
name: My Policy
version: "1.0"
tags: [production, api]
rules:
  - id: allow-read
    effect: allow
    actions: ["read", "list"]
    resource_types: ["document"]
    conditions:
      - key: resource.visibility
        op: eq
        value: public
```

## Rule Fields

- `id`: Unique rule identifier
- `effect`: "allow" or "deny"
- `actions`: List of action patterns (supports wildcards)
- `resource_types`: List of resource type patterns
- `resource_ids`: Optional specific resource IDs
- `conditions`: List of condition checks
- `obligations`: Actions to perform if rule matches

## Condition Operators

- `eq`: Equal to value
- `ne`: Not equal to value
- `in`: Value in list
- `contains`: List contains value
- `exists`: Key exists (value ignored)

## Evaluation Order

1. Explicit deny rules checked first
2. Then allow rules
3. Default deny if no match
"""

ROLE_SYNTAX = """
# Role Definitions

Roles group permissions for assignment to principals.

## Structure

```yaml
id: editor
name: Editor Role
description: Can read and write documents
permissions:
  - document:read
  - document:write
  - document:list
inherits:
  - viewer  # Inherit viewer permissions
```

## Fields

- `id`: Unique role identifier
- `name`: Human-readable name
- `description`: Role purpose
- `permissions`: List of permission strings
- `inherits`: List of role IDs to inherit from

## Permission Format

`<resource_type>:<action>` or `<resource_type>:*` for all actions.
"""

INTEGRATION_PATTERNS = """
# Integration Patterns

## With Auth Brick

```python
# After auth validates token, use principal for permissions
envelope = {"principal_id": token.sub, "tenant_id": token.tenant}
result = permissions.evaluate(
    action="write",
    resource={"type": "document", "id": doc_id},
    envelope=envelope
)
```

## With Workflow Brick

```python
# Gate workflow steps with permission checks
if permissions.evaluate(action="approve", resource=workflow_resource):
    workflow.step_run(run_id)
```

## Audit Integration

All evaluations are logged to the audit store with:
- Timestamp, action, resource
- Decision and reason
- Principal and tenant
- Matched policy/rule IDs
"""

DOCS = {
    "overview": PERMISSIONS_OVERVIEW,
    "policy-syntax": POLICY_SYNTAX,
    "role-syntax": ROLE_SYNTAX,
    "integration": INTEGRATION_PATTERNS,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
