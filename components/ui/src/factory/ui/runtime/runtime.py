"""Runtime orchestrator for UI module."""

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .adapters import InlineHtmlRenderAdapter, JsonAdapter
from .config import ConfigLoader, UISettings
from .push_channel import PushChannel
from .registry import ComponentRegistry
from .store.view_store import InMemoryViewStore
from .view_manager import ViewManager
from .runtime_ops import RuntimeOperations, __version__

logger = logging.getLogger(__name__)


class UIRuntime:
    """Main runtime for UI module."""

    def __init__(self, config_dir: str | Path | None = None):
        self.config_loader = ConfigLoader(config_dir)
        self.settings: UISettings | None = None
        self.view_manager: ViewManager | None = None
        self._initialized = False
        self._started_at: datetime | None = None
        self._last_error: str | None = None
        self._running_mode = "stdio"
        self._ops: RuntimeOperations | None = None

    def initialize(self) -> None:
        if self._initialized:
            return

        try:
            self.settings = self.config_loader.load_settings()
            registry = ComponentRegistry()
            store = InMemoryViewStore()
            push_channel = PushChannel()

            self.view_manager = ViewManager(store=store, push_channel=push_channel, registry=registry)

            if "json" in self.settings.enabled_adapters:
                self.view_manager.register_adapter(JsonAdapter())
            if "inline-html" in self.settings.enabled_adapters:
                self.view_manager.register_adapter(InlineHtmlRenderAdapter())

            view_definitions = self.config_loader.load_view_definitions()
            for view_def in view_definitions.values():
                view = view_def.to_view()
                self.view_manager.store.save(view)
                logger.info(f"Loaded view from config: {view.id}")

            self._ops = RuntimeOperations(self)
            self._initialized = True
            self._started_at = datetime.now(timezone.utc)
            logger.info("UI Runtime initialized")

        except Exception as e:
            self._last_error = str(e)
            logger.error(f"Failed to initialize runtime: {e}")
            raise

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self.initialize()

    def get_capabilities(self) -> dict[str, Any]:
        self._ensure_initialized()
        return self._ops.get_capabilities()

    def health_check(self) -> dict[str, Any]:
        return self._ops.health_check() if self._ops else {"status": "not_initialized"}

    def describe_config_schema(self) -> dict[str, Any]:
        return self.config_loader.get_config_schema()

    def get_view_registry(self) -> dict[str, Any]:
        self._ensure_initialized()
        return self._ops.get_view_registry()

    def get_authoring_status(self) -> dict[str, Any]:
        return self._ops.get_authoring_status() if self._ops else {"enabled": False}


_runtime: UIRuntime | None = None


def get_runtime(config_dir: str | Path | None = None) -> UIRuntime:
    global _runtime
    if _runtime is None:
        _runtime = UIRuntime(config_dir)
        _runtime.initialize()
    return _runtime


def reset_runtime() -> None:
    global _runtime
    _runtime = None
