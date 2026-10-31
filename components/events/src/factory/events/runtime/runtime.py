"""Events runtime - orchestrates event publishing and subscription management."""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import yaml

from .envelope import ContextEnvelope
from .history import EventHistoryEntry
from .models import Event, EventResult
from .ports import EventHistoryStore, EventStore
from .adapters import InMemoryEventStore
from .store_factory import (
    create_event_store,
    create_history_store,
    load_history_retention_days,
    load_store_config,
)
from .subscriptions import SubscriptionDefinition, SubscriptionRegistry


class EventsRuntime:
    """Runtime for event publishing and subscription management."""

    _instance: EventStore | None = None  # Singleton for testing

    def __init__(self, config_dir: str | Path) -> None:
        self._config_dir = Path(config_dir)
        store_backend, store_cfg = load_store_config(self._config_dir)
        self._history_retention_days = load_history_retention_days(store_cfg)
        self._event_store: EventStore = create_event_store(store_backend, store_cfg)
        self._history_store: EventHistoryStore = create_history_store(store_backend, store_cfg)
        self._subscription_registry = SubscriptionRegistry()
        self._last_history_prune_at: datetime | None = None
        self._prune_interval = timedelta(minutes=5)
        self._prune_history_if_needed(force=True)
        self._load_config()

    @classmethod
    def reset(cls) -> None:
        cls._instance = None

    @classmethod
    async def get_store(cls) -> EventStore:
        if cls._instance is None:
            cls._instance = InMemoryEventStore()
            await cls._instance.initialize()
        return cls._instance

    def _load_config(self) -> None:
        """Load subscriptions from config and built-in directories."""
        self._load_subs_from(self._config_dir / "subscriptions")
        self._load_subs_from(Path(__file__).parent.parent / "subscriptions")

    def _load_subs_from(self, directory: Path) -> None:
        """Load subscription YAML files from a directory."""
        if not directory.exists():
            return
        for f in directory.glob("*.yaml"):
            try:
                data = yaml.safe_load(f.read_text())
                if data:
                    self._subscription_registry.register(
                        SubscriptionDefinition.model_validate(data))
            except Exception:
                pass

    @classmethod
    def from_config_dir(cls, config_dir: str | Path) -> EventsRuntime:
        return cls(config_dir)

    def set_event_store(self, store: EventStore) -> None:
        self._event_store = store

    def _prune_history_if_needed(self, force: bool = False) -> int:
        """Prune history if a retention window is configured and pruning is due."""
        if self._history_retention_days is None:
            return 0
        now = datetime.now(timezone.utc)
        if not force and self._last_history_prune_at is not None:
            if now - self._last_history_prune_at < self._prune_interval:
                return 0
        cutoff = now - timedelta(days=self._history_retention_days)
        deleted = self._history_store.prune(cutoff)
        self._last_history_prune_at = now
        return deleted

    def set_history_store(self, store: EventHistoryStore) -> None:
        self._history_store = store
        self._prune_history_if_needed(force=True)

    def get_subscription_registry(self) -> SubscriptionRegistry:
        return self._subscription_registry

    def publish(self, event_type: str, payload: dict[str, Any],
                source: str, envelope: ContextEnvelope | None = None) -> EventResult:
        """Publish an event to store, history, SSE bridge, and subscriptions."""
        event_id = str(uuid.uuid4())
        timestamp = datetime.now(timezone.utc)
        event = Event(id=event_id, type=event_type, payload=payload,
                      source=source, timestamp=timestamp)
        self._event_store.store(event)
        from .bridge import bridge_to_event_bus
        bridge_to_event_bus(event_type, payload, source, timestamp)
        self._history_store.record(EventHistoryEntry(
            event_id=event_id, event_type=event_type, payload=payload,
            source=source, timestamp=timestamp,
            tenant_id=envelope.tenant_id if envelope else None,
            principal_id=envelope.principal_id if envelope else None,
            correlation_id=envelope.request_id if envelope else None,
            metadata=envelope.attributes if envelope else {},
        ))
        self._prune_history_if_needed()
        matching_subs = self._subscription_registry.find_matching(event_type)
        dispatched = 0
        for sub in matching_subs:
            if sub.handler.startswith("mcp:"):
                from .dispatch import dispatch_mcp_handler
                if dispatch_mcp_handler(sub, event):
                    dispatched += 1
        return EventResult(
            event_id=event_id, status="published",
            subscriptions_matched=len(matching_subs),
            subscriptions_dispatched=dispatched, timestamp=timestamp.isoformat(),
        )

    def get_event(self, event_id: str) -> Event | None:
        return self._event_store.get(event_id)

    def list_events(self, event_type: str | None = None,
                    source: str | None = None, limit: int = 100) -> list[Event]:
        return self._event_store.list_events(event_type=event_type, source=source, limit=limit)

    def list_event_history(self, event_type: str | None = None,
                           source: str | None = None, tenant_id: str | None = None,
                           limit: int = 100) -> list[EventHistoryEntry]:
        return self._history_store.list_entries(
            event_type=event_type, source=source, tenant_id=tenant_id, limit=limit)

    def replay_event(self, event_id: str,
                     envelope: ContextEnvelope | None = None) -> EventResult | None:
        entry = self._history_store.get(event_id)
        if not entry:
            return None
        stored_attributes = dict(entry.metadata)
        current = envelope or ContextEnvelope()
        replay_envelope = current.model_copy(update={
            "tenant_id": current.tenant_id or entry.tenant_id,
            "principal_id": current.principal_id or entry.principal_id,
            "request_id": current.request_id or entry.correlation_id,
            "attributes": {**stored_attributes, **current.attributes},
        })
        return self.publish(event_type=entry.event_type, payload=entry.payload,
                            source=f"{entry.source}:replay", envelope=replay_envelope)

    def prune_event_history(self, older_than: datetime | None = None) -> int:
        """Prune event history either by explicit cutoff or configured retention."""
        if older_than is None:
            if self._history_retention_days is None:
                return 0
            older_than = datetime.now(timezone.utc) - timedelta(days=self._history_retention_days)
        deleted = self._history_store.prune(older_than)
        self._last_history_prune_at = datetime.now(timezone.utc)
        return deleted

    def count_event_history(self) -> int:
        """Count total event history entries."""
        return self._history_store.count()

    def get_history_retention_days(self) -> int | None:
        """Return configured history retention window in days, if any."""
        return self._history_retention_days
