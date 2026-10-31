"""MCP Prompt registration for permissions brick."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .templates import PROMPT_TEMPLATES

if TYPE_CHECKING:
    from factory.permissions.runtime.runtime import PermissionsRuntime


def register(mcp: Any, runtime: "PermissionsRuntime") -> None:
    """Register all permissions prompts with the MCP server."""

    @mcp.prompt()
    def create_policy(
        name: str,
        purpose: str = "",
        resource_type: str = "document",
        tags: str = "general",
    ) -> str:
        """Generate guidance for creating a new access control policy."""
        policy_id = name.lower().replace(" ", "-").replace("_", "-")
        
        rules_yaml = f"""  - id: allow-read
    effect: allow
    actions: ["read", "list"]
    resource_types: ["{resource_type}"]
  - id: deny-delete
    effect: deny
    actions: ["delete"]
    resource_types: ["{resource_type}"]
    conditions:
      - key: resource.owner
        op: ne
        value: "{{{{envelope.principal_id}}}}\""""
        
        return PROMPT_TEMPLATES["create_policy"]["template"].format(
            name=name,
            id=policy_id,
            purpose=purpose or f"Access control for {resource_type} resources",
            tags=tags,
            rules_yaml=rules_yaml,
            test_action="read",
            resource_type=resource_type,
        )

    @mcp.prompt()
    def debug_denial(
        action: str = "read",
        resource_type: str = "document",
        resource_id: str = "unknown",
        principal_id: str = "unknown",
    ) -> str:
        """Generate guidance for debugging a permission denial."""
        return PROMPT_TEMPLATES["debug_denial"]["template"].format(
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            principal_id=principal_id,
        )

    @mcp.prompt()
    def setup_rbac(resource_types: str = "document,folder") -> str:
        """Generate guidance for setting up role-based access control."""
        types_list = [t.strip() for t in resource_types.split(",")]
        
        return f"""# Setup Role-Based Access Control

## Step 1: Define Roles

Create role files in `config/roles/`:

### viewer.yaml
```yaml
id: viewer
name: Viewer
description: Read-only access
permissions:
{chr(10).join(f'  - {t}:read' for t in types_list)}
{chr(10).join(f'  - {t}:list' for t in types_list)}
```

### editor.yaml
```yaml
id: editor
name: Editor
description: Read and write access
permissions:
{chr(10).join(f'  - {t}:read' for t in types_list)}
{chr(10).join(f'  - {t}:write' for t in types_list)}
{chr(10).join(f'  - {t}:list' for t in types_list)}
inherits:
  - viewer
```

### admin.yaml
```yaml
id: admin
name: Administrator
description: Full access
permissions:
{chr(10).join(f'  - {t}:*' for t in types_list)}
inherits:
  - editor
```

## Step 2: Create Policies

Create policies that reference roles or use direct rules.

## Step 3: Verify

```
permissions.get_role_registry()
permissions.evaluate(action="read", resource={{"type": "{types_list[0]}"}})
```
"""

    @mcp.prompt()
    def audit_review(
        time_range: str = "last 24 hours",
        principal_id: str = "",
        resource_type: str = "",
    ) -> str:
        """Generate guidance for reviewing permission audit logs."""
        return PROMPT_TEMPLATES["audit_review"]["template"].format(
            time_range=time_range,
            principal_id=principal_id or "all",
            resource_type=resource_type or "all",
        )
