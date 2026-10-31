"""Documentation content for notification MCP resources."""

from __future__ import annotations

OVERVIEW_DOC = """# Notification Brick

Notification delivery and alert management with pluggable channel backends.

## Key Concepts

### Channels
Delivery backends (email, SMS, Slack, webhook). Each channel has:
- Type (smtp, twilio, slack, webhook, console)
- Configuration (credentials, endpoints)
- Enabled status

### Templates
Reusable notification templates with variable substitution.
- Name and body content
- Optional subject line
- Variable placeholders

### Deliveries
Track notification delivery status:
- `queued` - Pending delivery
- `sent` - Sent to backend
- `delivered` - Confirmed delivery
- `failed` - Delivery failed

## MCP Tools

### Deterministic
- `get_capabilities` - Module capabilities
- `health_check` - Backend connectivity
- `get_channel_registry` - List channels
- `get_template_registry` - List templates
- `describe_config_schema` - Configuration schemas

### Operational
- `send_notification` - Send notification
- `get_delivery_status` - Check delivery status
- `list_deliveries` - List delivery history

### Authoring
- `upsert_channel_config` - Create/update channel
- `delete_channel_config` - Remove channel
- `upsert_template_config` - Create/update template
- `delete_template_config` - Remove template
"""

CHANNELS_DOC = """# Notification Channels

## Supported Channel Types

### SMTP (Email)
```yaml
type: smtp
config:
  host: smtp.example.com
  port: 587
  username: user@example.com
  password: secret
  from_address: noreply@example.com
  use_tls: true
```

### Twilio (SMS)
```yaml
type: twilio
config:
  account_sid: AC...
  auth_token: secret
  from_number: +1234567890
```

### Slack
```yaml
type: slack
config:
  webhook_url: https://hooks.slack.com/...
  default_channel: "#alerts"
```

### Webhook
```yaml
type: webhook
config:
  url: https://api.example.com/notify
  headers:
    Authorization: Bearer token
```

### Console (Testing)
```yaml
type: console
config: {}
```
"""

TEMPLATES_DOC = """# Notification Templates

## Template Structure
```yaml
template_id: welcome
name: Welcome Email
subject: Welcome to {{app_name}}!
body: |
  Hello {{user_name}},
  Welcome to {{app_name}}. Your account is ready.
variables:
  - app_name
  - user_name
```

## Variable Substitution
Use `{{variable}}` syntax in templates. Variables are replaced
with values from the `data` parameter when sending.

## Usage
```python
send_notification(
    recipient="user@example.com",
    template_id="welcome",
    data={"app_name": "MyApp", "user_name": "John"}
)
```
"""

ENVELOPE_DOC = """# Notification Envelope

Context envelope for tracking and multi-tenancy.

## Fields
- `request_id`: Unique request identifier
- `tenant_id`: Multi-tenant isolation
- `principal_id`: Sender identity
- `correlation_id`: Cross-service tracing
- `metadata`: Additional context

## Usage
```python
send_notification(
    recipient="user@example.com",
    content="Hello!",
    envelope={
        "tenant_id": "acme-corp",
        "correlation_id": "trace-123"
    }
)
```
"""

DOCS = {
    "overview": OVERVIEW_DOC,
    "channels": CHANNELS_DOC,
    "templates": TEMPLATES_DOC,
    "envelope": ENVELOPE_DOC,
}


def get_doc(name: str) -> str | None:
    """Get documentation by name."""
    return DOCS.get(name)


def list_docs() -> list[str]:
    """List available documentation."""
    return list(DOCS.keys())
