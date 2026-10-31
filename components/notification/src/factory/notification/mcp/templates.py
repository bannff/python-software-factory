"""Prompt templates for notification MCP prompts."""

from __future__ import annotations

CONFIGURE_CHANNEL_TEMPLATE = """# Configure Notification Channel: {channel_id}

## Channel Type: {channel_type}

## Steps

1. **Create Channel Config**
   ```
   upsert_channel_config(
       channel_id="{channel_id}",
       type="{channel_type}",
       config={config_example},
       enabled=True
   )
   ```

2. **Verify Channel**
   ```
   get_channel_registry()
   ```

3. **Test Notification**
   ```
   send_notification(
       recipient="{test_recipient}",
       content="Test notification",
       channel_id="{channel_id}"
   )
   ```

## Configuration Notes
{config_notes}
"""

DEBUG_DELIVERY_TEMPLATE = """# Debug Notification Delivery

## Delivery Info
- Message ID: {message_id}
- Status: {status}
- Backend: {backend}

## Diagnostic Steps

1. **Check Delivery Status**
   ```
   get_delivery_status(message_id="{message_id}")
   ```

2. **Check Channel Health**
   ```
   health_check()
   ```

3. **Review Channel Config**
   ```
   get_channel_registry()
   ```

## Common Issues

- **queued**: Check backend connectivity
- **failed**: Review error message, verify credentials
- **sent but not delivered**: Check recipient address

## Next: {next_steps}
"""

CREATE_TEMPLATE_TEMPLATE = """# Create Notification Template

## Template: {template_id}

## Steps

1. **Create Template**
   ```
   upsert_template_config(
       template_id="{template_id}",
       name="{name}",
       subject="{subject}",
       body=\"\"\"
{body}
\"\"\",
       variables={variables}
   )
   ```

2. **Verify Template**
   ```
   get_template_registry()
   ```

3. **Test Template**
   ```
   send_notification(
       recipient="test@example.com",
       template_id="{template_id}",
       data={test_data}
   )
   ```

## Variable Syntax
Use `{{{{variable}}}}` for placeholders in body and subject.
"""


def get_configure_channel_prompt(
    channel_id: str = "my_channel",
    channel_type: str = "smtp",
) -> str:
    """Generate channel configuration prompt."""
    config_examples = {
        "smtp": '{"host": "smtp.example.com", "port": 587, "username": "...", "password": "..."}',
        "twilio": '{"account_sid": "AC...", "auth_token": "...", "from_number": "+1..."}',
        "slack": '{"webhook_url": "https://hooks.slack.com/..."}',
        "webhook": '{"url": "https://api.example.com/notify"}',
        "console": "{}",
    }
    test_recipients = {
        "smtp": "user@example.com",
        "twilio": "+1234567890",
        "slack": "#general",
        "webhook": "endpoint",
        "console": "test",
    }
    notes = {
        "smtp": "Ensure SMTP server allows connections. Use TLS for security.",
        "twilio": "Get credentials from Twilio Console. Verify phone number.",
        "slack": "Create incoming webhook in Slack App settings.",
        "webhook": "Ensure endpoint accepts POST with JSON body.",
        "console": "Console channel logs to stdout. Use for testing only.",
    }

    return CONFIGURE_CHANNEL_TEMPLATE.format(
        channel_id=channel_id,
        channel_type=channel_type,
        config_example=config_examples.get(channel_type, "{}"),
        test_recipient=test_recipients.get(channel_type, "test"),
        config_notes=notes.get(channel_type, ""),
    )


def get_debug_delivery_prompt(
    message_id: str = "msg_xxx",
    status: str = "failed",
    backend: str = "smtp",
) -> str:
    """Generate delivery debugging prompt."""
    next_steps = {
        "queued": "Check backend connectivity and retry",
        "sent": "Wait for delivery confirmation",
        "delivered": "Notification delivered successfully",
        "failed": "Review error, fix config, and retry",
    }.get(status, "Check delivery status")

    return DEBUG_DELIVERY_TEMPLATE.format(
        message_id=message_id,
        status=status,
        backend=backend,
        next_steps=next_steps,
    )


def get_create_template_prompt(
    template_id: str = "welcome",
    name: str = "Welcome Email",
) -> str:
    """Generate template creation prompt."""
    return CREATE_TEMPLATE_TEMPLATE.format(
        template_id=template_id,
        name=name,
        subject="Welcome to {{app_name}}!",
        body="Hello {{user_name}},\\n\\nWelcome to {{app_name}}!",
        variables='["app_name", "user_name"]',
        test_data='{"app_name": "MyApp", "user_name": "John"}',
    )
