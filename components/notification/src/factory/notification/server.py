"""FastMCP Server interface exposing notification tools.

This module is the public MCP surface. It must not contain domain logic.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .runtime.dispatcher import NotificationRuntime
from .runtime.adapters.inbox_store_sql import SqlInboxStore
from .runtime.adapters.prefs_store_sql import SqlPreferencesStore
from .authoring import AuthoringRuntime
from .mcp import (
    deterministic, operational, authoring, resources, prompts,
    inbox_deterministic, inbox_operational, inbox_publish, inbox_resolve,
    prefs_deterministic, prefs_operational,
)


def get_runtime() -> NotificationRuntime:
    """Create a default NotificationRuntime from environment / defaults."""
    config_dir = Path(os.environ.get("NOTIFICATION_CONFIG_DIR", "./config"))
    inbox_db = os.environ.get("NOTIFICATION_INBOX_DB_PATH", "./.storage/notification.db")
    prefs_db = os.environ.get(
        "NOTIFICATION_PREFS_DB_PATH", "./.storage/notification-prefs.db")
    return NotificationRuntime(
        config_dir, inbox_store=SqlInboxStore(db_path=inbox_db),
        prefs_store=SqlPreferencesStore(db_path=prefs_db),
    )


def _initialize(runtime: NotificationRuntime) -> None:
    import asyncio
    try:
        asyncio.get_running_loop()
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            pool.submit(asyncio.run, runtime.initialize()).result()
    except RuntimeError:
        asyncio.run(runtime.initialize())


def _register_tools(registry: Any, runtime: NotificationRuntime) -> None:
    enabled = os.environ.get("NOTIFY_ENABLE_AUTHORING_TOOLS") == "1"
    authoring_runtime = AuthoringRuntime(runtime.config_dir) if enabled else None
    deterministic.register(registry, runtime)
    operational.register(registry, runtime)
    inbox_deterministic.register(registry, runtime)
    inbox_operational.register(registry, runtime)
    inbox_resolve.register(registry, runtime)
    inbox_publish.register(registry, runtime)
    prefs_deterministic.register(registry, runtime)
    prefs_operational.register(registry, runtime)
    authoring.register(registry, runtime, authoring_runtime, enabled)


def create_tool_catalog(runtime: NotificationRuntime | None = None) -> Any:
    """Create the transport-neutral Notification tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime()
    _initialize(active_runtime)
    catalog = ToolCatalog("notification-module")
    _register_tools(catalog, active_runtime)
    resources.register(catalog, active_runtime)
    prompts.register(catalog, active_runtime)
    return catalog


def create_mcp_server(runtime: NotificationRuntime | None = None) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for notification brick."""
    return {
        "name": "notification",
        "version": "1.0.0",
        "backends": ["email_smtp", "sms_twilio", "slack_webhooks"],
        "features": ["notifications", "alerts", "messaging", "templates", "inbox"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for notification brick."""
    return {"healthy": True, "channels": ["email", "sms", "slack"]}


def describe_config_schema() -> dict[str, Any]:
    """Describe notification configuration schema."""
    return {
        "type": "object",
        "properties": {
            "channels": {"type": "array", "items": {"type": "string", "enum": ["email", "sms", "slack"]}},
            "default_channel": {"type": "string"},
        },
    }
