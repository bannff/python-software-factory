"""Event store + history store factory helpers.

Centralises backend wiring for ``EventsRuntime``. Resolves the active
backend via the magnets path (``events.backend`` → InfraEnv → settings)
and constructs the matching :class:`EventStore` and
:class:`EventHistoryStore` implementations.

Keeping this out of ``runtime.py`` keeps that file under the 200 LOC
ceiling and prevents server.py from re-implementing the switch.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .history import InMemoryEventHistoryStore, SQLiteEventHistoryStore
from .ports import EventHistoryStore, EventStore
from .adapters import InMemoryEventStore


def load_store_config(config_dir: Path) -> tuple[str, dict[str, Any]]:
    """Resolve the active backend and raw event_store config.

    Resolution order (highest precedence first):
      1. ``EVENTS_BACKEND`` env var (via the InfraEnv config layer)
      2. ``event_store.backend`` from ``settings.yaml``
      3. Default ``"memory"``

    Other ``event_store`` keys (``db_path``, ``retention_days`` …) always
    come from ``settings.yaml`` so file-driven retention survives an
    env-only backend override.
    """
    from factory.mcp_utils.interface import get_infra

    settings_path = config_dir / "settings.yaml"
    store_cfg: dict[str, Any] = {}
    if settings_path.exists():
        data = yaml.safe_load(settings_path.read_text())
        if isinstance(data, dict):
            event_store = data.get("event_store", {})
            if isinstance(event_store, dict):
                store_cfg = event_store

    settings_backend = store_cfg.get("backend", "memory")
    backend = get_infra("events.backend", settings_backend)
    return str(backend).lower(), store_cfg


def create_event_store(backend: str, store_cfg: dict[str, Any]) -> EventStore:
    """Build an event store for the given backend.

    Supported backends: ``memory`` (default), ``sqlite``, ``aws``,
    ``neo4j``, ``redis``. All wiring lives here — server.py is a pure
    factory shell and must not duplicate this switch.
    """
    if backend == "sqlite":
        from .adapters.sqlite import SQLiteEventStore
        db_path = store_cfg.get("db_path") if isinstance(store_cfg, dict) else None
        return SQLiteEventStore(db_path=db_path)  # type: ignore[return-value]
    if backend == "aws":
        from .adapters.aws import AWSEventStore
        return AWSEventStore(  # type: ignore[return-value]
            **{k: v for k, v in store_cfg.items() if k != "backend"}
        )
    if backend == "neo4j":
        from factory.mcp_utils.interface import get_neo4j_config
        from .adapters.neo4j import Neo4jEventStore
        neo4j = get_neo4j_config()
        return Neo4jEventStore(  # type: ignore[return-value]
            uri=neo4j["uri"],
            auth=(neo4j["user"], neo4j["password"]),
            database=neo4j["database"],
        )
    if backend == "redis":
        from factory.mcp_utils.interface import get_infra
        from .adapters.redis import RedisEventStore
        return RedisEventStore(  # type: ignore[return-value]
            url=get_infra("redis.url", "redis://localhost:6379/0"),
        )
    return InMemoryEventStore()


def create_history_store(backend: str, store_cfg: dict[str, Any]) -> EventHistoryStore:
    """Build a history store aligned with the event store.

    Only ``sqlite`` has a dedicated durable history backend today.
    ``memory``, ``aws``, ``neo4j`` and ``redis`` fall through to
    :class:`InMemoryEventHistoryStore` until matching adapters land.
    """
    if backend == "sqlite":
        db_path = store_cfg.get("db_path") if isinstance(store_cfg, dict) else None
        return SQLiteEventHistoryStore(db_path=db_path)
    return InMemoryEventHistoryStore()


def load_history_retention_days(store_cfg: dict[str, Any]) -> int | None:
    """Parse the configured history retention window in days, if any."""
    raw_value = store_cfg.get("retention_days") if isinstance(store_cfg, dict) else None
    if raw_value in (None, "", 0, "0"):
        return None
    try:
        retention_days = int(raw_value)
    except (TypeError, ValueError):
        return None
    return retention_days if retention_days > 0 else None


__all__ = [
    "load_store_config",
    "create_event_store",
    "create_history_store",
    "load_history_retention_days",
]
