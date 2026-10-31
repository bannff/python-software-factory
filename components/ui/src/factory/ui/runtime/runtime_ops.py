"""Runtime operations for UI module."""

from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .runtime import UIRuntime

__version__ = "0.2.0"
SCHEMA_VERSION = "1.0.0"


class RuntimeOperations:
    """Operations for UI runtime."""

    def __init__(self, runtime: "UIRuntime"):
        self._runtime = runtime

    def get_capabilities(self) -> dict[str, Any]:
        settings = self._runtime.settings
        view_manager = self._runtime.view_manager
        return {
            "module": "ui-module",
            "version": __version__,
            "schema_version": SCHEMA_VERSION,
            "running_mode": self._runtime._running_mode,
            "authoring_enabled": settings.authoring_enabled if settings else False,
            "adapters": {
                "available": view_manager.list_adapters() if view_manager else [],
                "default": settings.default_adapter if settings else "json",
            },
            "storage": {"backend": settings.storage_backend if settings else "memory"},
            "push": {
                "enabled": settings.push_enabled if settings else True,
                "max_clients": settings.max_clients if settings else 100,
            },
            "limits": {
                "max_views": settings.max_views if settings else 1000,
                "max_components_per_view": settings.max_components_per_view if settings else 100,
            },
            "feature_flags": settings.feature_flags if settings else {},
            "component_types": [
                c.component_type.value
                for c in (view_manager.registry.list_components() if view_manager else [])
            ],
        }

    def health_check(self) -> dict[str, Any]:
        status = "healthy"
        checks = {}

        if not self._runtime._initialized:
            return {
                "status": "unhealthy",
                "checks": {"initialized": {"status": "not_initialized"}},
                "uptime_seconds": None,
                "last_error": self._runtime._last_error,
            }

        checks["initialized"] = {"status": "ok"}

        try:
            if self._runtime.view_manager:
                view_count = len(self._runtime.view_manager.store.list_views())
                checks["store"] = {"status": "ok", "view_count": view_count}
            else:
                checks["store"] = {"status": "not_initialized"}
                status = "degraded"
        except Exception as e:
            checks["store"] = {"status": "error", "error": str(e)}
            status = "unhealthy"

        try:
            if self._runtime.view_manager:
                client_count = len(self._runtime.view_manager.push_channel.list_clients())
                checks["push_channel"] = {"status": "ok", "connected_clients": client_count}
            else:
                checks["push_channel"] = {"status": "not_initialized"}
        except Exception as e:
            checks["push_channel"] = {"status": "error", "error": str(e)}
            status = "degraded"

        uptime_seconds = None
        if self._runtime._started_at:
            uptime_seconds = (datetime.now(timezone.utc) - self._runtime._started_at).total_seconds()

        return {
            "status": status,
            "checks": checks,
            "uptime_seconds": uptime_seconds,
            "started_at": self._runtime._started_at.isoformat() if self._runtime._started_at else None,
            "last_error": self._runtime._last_error,
        }

    def get_view_registry(self) -> dict[str, Any]:
        views = []
        if self._runtime.view_manager:
            for view in self._runtime.view_manager.list_views():
                views.append({
                    "id": view.id, "name": view.name, "version": view.version,
                    "component_count": len(view.components),
                    "tags": view.metadata.get("tags", []),
                    "updated_at": view.updated_at.isoformat(),
                })
        return {
            "views": views, "total": len(views),
            "config_dir": str(self._runtime.config_loader.config_dir),
        }

    def get_authoring_status(self) -> dict[str, Any]:
        return {
            "enabled": self._runtime.settings.authoring_enabled if self._runtime.settings else False,
            "config_dir": str(self._runtime.config_loader.config_dir),
            "views_dir": str(self._runtime.config_loader.config_dir / "views"),
            "schema_version": SCHEMA_VERSION,
        }
