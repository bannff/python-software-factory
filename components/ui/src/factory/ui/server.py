"""MCP Server for UI Module (Modular Registry)."""

import logging
import os
from typing import Any

from .runtime.envelope import ContextEnvelope
from .runtime.runtime import UIRuntime, get_runtime
from .mcp import resources, prompts
from .mcp import tools
from factory.mcp_utils.server import make_lazy_runner

logger = logging.getLogger(__name__)


def _register_tools(registry: Any, runtime: UIRuntime, chat_store: Any) -> None:
    get_current = lambda: runtime
    parse_envelope = lambda envelope: ContextEnvelope.from_dict(envelope)

    def is_authoring_enabled() -> bool:
        return (
            os.environ.get("AUTHORING_ENABLED", "").lower() == "true"
            or bool(runtime.settings and runtime.settings.authoring_enabled)
        )

    tools.register(registry, get_current, parse_envelope, is_authoring_enabled, chat_store)


def create_tool_catalog(
    runtime: UIRuntime | None = None, chat_store: Any | None = None,
) -> Any:
    """Create the transport-neutral UI tool catalog."""
    from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

    active_runtime = runtime or get_runtime(os.environ.get("UI_CONFIG_DIR"))
    if chat_store is None:
        if runtime is not None:
            from .runtime.chat_preferences import InMemoryChatPreferenceStore
            chat_store = InMemoryChatPreferenceStore()
        else:
            from .runtime.adapters.chat_preferences_sqlite import SqliteChatPreferenceStore
            path = os.environ.get(
                "COMPANION_X_UI_PREFERENCES_DB_PATH", "./.storage/ui-preferences.db",
            )
            chat_store = SqliteChatPreferenceStore(path)
    catalog = ToolCatalog("ui-module")
    _register_tools(catalog, active_runtime, chat_store)
    resources.register(catalog, lambda: active_runtime)
    prompts.register(catalog)
    return catalog


def create_mcp_server(
    runtime: UIRuntime | None = None, chat_store: Any | None = None,
) -> Any:
    """Return the canonical framework-neutral catalog."""
    return create_tool_catalog(runtime, chat_store)


def get_capabilities() -> dict[str, Any]:
    """Return machine-readable capabilities for ui brick."""
    return {
        "name": "ui",
        "version": "1.0.0",
        "backends": ["htmx", "react", "a2ui", "flet", "hybrid"],
        "features": ["ui_components", "polymorphic_adapters", "a2ui_protocol", "flet_flutter", "theme_system"],
    }


def health_check() -> dict[str, Any]:
    """Fast readiness probe for ui brick."""
    return {"healthy": True, "adapter": "htmx"}


def describe_config_schema() -> dict[str, Any]:
    """Describe ui configuration schema."""
    return {
        "type": "object",
        "properties": {
            "adapter": {"type": "string", "enum": ["htmx", "react", "a2ui", "flet", "hybrid"]},
            "theme": {"type": "string", "description": "UI theme name"},
        },
    }


get_mcp_server, main = make_lazy_runner(create_mcp_server)

if __name__ == "__main__":
    main()
