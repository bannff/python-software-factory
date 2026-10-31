"""Notification dispatcher runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from factory.notification.runtime.models import NotificationRequest, DeliveryStatus
from factory.notification.runtime.config import Settings, SCHEMA_VERSION
from factory.notification.runtime.channels import ChannelRegistry
from factory.notification.runtime.templates import TemplateRegistry
from factory.notification.runtime.delivery import DeliveryStore, InMemoryDeliveryStore
from factory.notification.runtime.backends.base import NotificationBackend
from factory.notification.runtime.backends.local import StdioBackend
from factory.notification.runtime.dispatcher_ops import DispatcherOperations
from factory.notification.runtime.adapters.inbox_store_sql import SqlInboxStore
from factory.notification.runtime.adapters.prefs_store_sql import SqlPreferencesStore
from factory.notification.runtime.inbox_models import NotificationRecord, Priority
from factory.notification.runtime.prefs_models import NotificationPreferences
from factory.notification.runtime.inbox_ops import InboxOperations
from factory.notification.runtime.ports import InboxStore, PreferencesStore


class NotificationRuntime:
    """Main notification runtime."""

    def __init__(
        self, config_dir: Path, *, inbox_store: InboxStore | None = None,
        prefs_store: PreferencesStore | None = None,
    ):
        self.config_dir = Path(config_dir)
        self.settings: Settings | None = None
        self.settings_raw: dict[str, Any] | None = None
        self.channels: ChannelRegistry | None = None
        self.templates: TemplateRegistry | None = None
        self.delivery_store: DeliveryStore = InMemoryDeliveryStore()
        self.backend: NotificationBackend | None = None
        self._ops: DispatcherOperations | None = None
        # Durable inbox is independent of delivery. When not injected, default
        # to an isolated durable DB under the config dir so direct tests (temp
        # config dirs) never share state; the server injects an env-pathed store.
        self.inbox_store: InboxStore = inbox_store or SqlInboxStore(
            db_path=str(self.config_dir / "notification-inbox.db"))
        self._inbox = InboxOperations(self.inbox_store)
        self.prefs_store: PreferencesStore = prefs_store or SqlPreferencesStore(
            db_path=str(self.config_dir / "notification-prefs.db"))

    async def initialize(self) -> None:
        """Initialize the runtime with configuration."""
        self.settings_raw = self._read_settings_raw()
        self.settings = Settings.model_validate(self.settings_raw)
        self.channels = ChannelRegistry(self.config_dir)
        self.templates = TemplateRegistry(self.config_dir)
        self.backend = StdioBackend()
        await self.backend.initialize({})
        self._ops = DispatcherOperations(self)

    def _read_settings_raw(self) -> dict[str, Any]:
        """Read raw settings from YAML."""
        path = self.config_dir / "settings.yaml"
        if not path.exists():
            return {"service": {"name": "notification-module"}}
        data = yaml.safe_load(path.read_text())
        if not isinstance(data, dict):
            return {"service": {"name": "notification-module"}}
        if "service" not in data:
            data["service"] = {"name": data.get("module", {}).get("name", "notification-module")}
        return data

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "module": "notification-module", "version": "0.2.0",
            "deterministic_tools": ["get_capabilities", "health_check", "get_channel_registry",
                                    "get_template_registry", "describe_config_schema",
                                    "inbox_list", "inbox_get", "inbox_resolve_target"],
            "operational_tools": ["send_notification", "get_delivery_status", "list_deliveries",
                                  "inbox_mark_read", "inbox_mark_all_read", "inbox_publish"],
            "authoring": {"env_var": "NOTIFY_ENABLE_AUTHORING_TOOLS", "config_dir": str(self.config_dir)},
        }

    async def health_check(self) -> dict[str, Any]:
        backend_healthy = await self.backend.health_check() if self.backend else False
        return {
            "ok": backend_healthy,
            "service": self.settings.service.model_dump() if self.settings else {},
            "backend": self.backend.name if self.backend else "none",
            "channels_loaded": len(self.channels.channels) if self.channels else 0,
            "templates_loaded": len(self.templates.templates) if self.templates else 0,
        }

    def get_channel_registry(self) -> list[dict[str, Any]]:
        return self.channels.as_list() if self.channels else []

    def get_template_registry(self) -> list[dict[str, Any]]:
        return self.templates.as_list() if self.templates else []

    def describe_config_schema(self) -> dict[str, Any]:
        from factory.notification.runtime.config import ChannelConfig, TemplateConfig
        return {
            "schema_version": SCHEMA_VERSION,
            "schemas": {"settings": Settings.model_json_schema(),
                        "channel": ChannelConfig.model_json_schema(),
                        "template": TemplateConfig.model_json_schema()},
        }

    # Delegate to operations
    async def send_notification(self, recipient: str, content: str | None = None,
                                subject: str | None = None, template_id: str | None = None,
                                channel_id: str | None = None, data: dict[str, Any] | None = None,
                                priority: str = "normal") -> dict[str, Any]:
        return await self._ops.send_notification(recipient, content, subject, template_id,
                                                  channel_id, data, priority)

    def get_delivery_status(self, message_id: str) -> dict[str, Any]:
        return self._ops.get_delivery_status(message_id)

    def list_deliveries(self, status: str | None = None, limit: int = 100, offset: int = 0) -> dict[str, Any]:
        return self._ops.list_deliveries(status, limit, offset)

    # Owner-scoped durable inbox delegates (tenant/owner from ambient identity).
    def inbox_list(self, tenant_id: str, owner_id: str, *, limit: int = 50,
                   offset: int = 0, unread_only: bool = False) -> list[NotificationRecord]:
        return self._inbox.list(tenant_id, owner_id, limit=limit, offset=offset,
                                unread_only=unread_only)

    def inbox_get(self, tenant_id: str, owner_id: str,
                  notification_id: str) -> NotificationRecord:
        return self._inbox.get(tenant_id, owner_id, notification_id)

    def inbox_mark_read(self, tenant_id: str, owner_id: str, notification_id: str, *,
                        expected_revision: int) -> NotificationRecord:
        return self._inbox.mark_read(tenant_id, owner_id, notification_id,
                                     expected_revision=expected_revision)

    def inbox_mark_all_read(self, tenant_id: str, owner_id: str, *,
                            expected_unread_count: int) -> int:
        return self._inbox.mark_all_read(tenant_id, owner_id,
                                         expected_unread_count=expected_unread_count)

    def prefs_get(self, tenant_id: str, owner_id: str) -> NotificationPreferences:
        return self.prefs_store.get(tenant_id, owner_id)

    def prefs_update(
        self, tenant_id: str, owner_id: str, *, global_muted: bool,
        muted_kinds: frozenset[str], priority_overrides: dict[str, Priority],
        expected_revision: int,
    ) -> NotificationPreferences:
        snapshot = NotificationPreferences(
            tenant_id=tenant_id, owner_id=owner_id, global_muted=global_muted,
            muted_kinds=muted_kinds, priority_overrides=priority_overrides,
            revision=expected_revision,
        )
        return self.prefs_store.put(snapshot, expected_revision=expected_revision)


class Dispatcher:
    """Backwards-compatible dispatcher wrapper."""

    def __init__(self) -> None:
        self.config_dir: Path | None = None
        self.backend: NotificationBackend | None = None

    async def initialize(self, config_dir: str | Path, settings: dict[str, Any] | None = None) -> None:
        self.config_dir = Path(config_dir)
        settings = settings or {}
        backend_settings = settings.get("backend", {})
        backend_type = backend_settings.get("type", "stdio")
        backend_config = backend_settings.get("config", {})

        if backend_type == "stdio":
            self.backend = StdioBackend()
        elif backend_type == "apprise":
            from factory.notification.runtime.backends.apprise_adapter import AppriseBackend
            self.backend = AppriseBackend()
        else:
            raise ValueError(f"Unsupported backend type: {backend_type}")
        await self.backend.initialize(backend_config)

    async def send(self, request: NotificationRequest) -> DeliveryStatus:
        if not self.backend:
            raise RuntimeError("Dispatcher not initialized")
        return await self.backend.send(request)

    async def health_check(self) -> bool:
        return await self.backend.health_check() if self.backend else False
