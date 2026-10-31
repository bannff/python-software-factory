"""Tests for event history."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
import yaml

from factory.events.runtime.history import (
    EventHistoryEntry,
    InMemoryEventHistoryStore,
    SQLiteEventHistoryStore,
)
from factory.events.runtime.runtime import EventsRuntime
from factory.events.runtime.ports import EventHistoryStore


class TestEventHistoryEntry:
    """Tests for EventHistoryEntry model."""

    def test_create_entry(self):
        """Test creating a history entry."""
        entry = EventHistoryEntry(
            event_id="evt-123",
            event_type="user.created",
            payload={"user_id": "u-1"},
            source="auth-module",
        )
        assert entry.event_id == "evt-123"
        assert entry.event_type == "user.created"
        assert entry.payload == {"user_id": "u-1"}
        assert entry.timestamp is not None

    def test_entry_with_metadata(self):
        """Test entry with metadata."""
        entry = EventHistoryEntry(
            event_id="evt-456",
            event_type="order.placed",
            payload={"order_id": "o-1"},
            source="orders",
            tenant_id="tenant-1",
            principal_id="user-1",
            correlation_id="req-123",
        )
        assert entry.tenant_id == "tenant-1"
        assert entry.principal_id == "user-1"
        assert entry.correlation_id == "req-123"


class TestInMemoryEventHistoryStore:
    """Tests for InMemoryEventHistoryStore."""

    def test_record_event(self):
        """Test recording an event."""
        store = InMemoryEventHistoryStore()
        entry = EventHistoryEntry(
            event_id="evt-1",
            event_type="test.event",
            payload={},
            source="test",
        )
        store.record(entry)
        entries = store.list_entries()
        assert len(entries) == 1
        assert entries[0].event_id == "evt-1"

    def test_get_by_id(self):
        """Test getting event by ID."""
        store = InMemoryEventHistoryStore()
        entry = EventHistoryEntry(
            event_id="evt-1",
            event_type="test.event",
            payload={},
            source="test",
        )
        store.record(entry)
        retrieved = store.get("evt-1")
        assert retrieved is not None
        assert retrieved.event_id == "evt-1"

    def test_filter_by_event_type(self):
        """Test filtering by event type."""
        store = InMemoryEventHistoryStore()
        store.record(
            EventHistoryEntry(
                event_id="evt-1", event_type="user.created", payload={}, source="test"
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-2", event_type="order.placed", payload={}, source="test"
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-3", event_type="user.updated", payload={}, source="test"
            )
        )

        user_events = store.list_entries(event_type="user.created")
        assert len(user_events) == 1
        assert user_events[0].event_id == "evt-1"

    def test_filter_by_source(self):
        """Test filtering by source."""
        store = InMemoryEventHistoryStore()
        store.record(
            EventHistoryEntry(
                event_id="evt-1", event_type="test", payload={}, source="auth"
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-2", event_type="test", payload={}, source="orders"
            )
        )

        auth_events = store.list_entries(source="auth")
        assert len(auth_events) == 1
        assert auth_events[0].source == "auth"

    def test_limit_results(self):
        """Test limiting results."""
        store = InMemoryEventHistoryStore()
        for i in range(10):
            store.record(
                EventHistoryEntry(
                    event_id=f"evt-{i}",
                    event_type="test",
                    payload={},
                    source="test",
                )
            )

        limited = store.list_entries(limit=5)
        assert len(limited) == 5

    def test_order_by_timestamp_desc(self):
        """Test ordering by timestamp descending."""
        store = InMemoryEventHistoryStore()
        store.record(
            EventHistoryEntry(
                event_id="evt-1", event_type="test", payload={}, source="test"
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-2", event_type="test", payload={}, source="test"
            )
        )

        entries = store.list_entries()
        # Most recent first
        assert entries[0].event_id == "evt-2"
        assert entries[1].event_id == "evt-1"

    def test_max_entries_limit(self):
        """Test max entries limit."""
        store = InMemoryEventHistoryStore(max_entries=5)
        for i in range(10):
            store.record(
                EventHistoryEntry(
                    event_id=f"evt-{i}",
                    event_type="test",
                    payload={},
                    source="test",
                )
            )

        # Should only keep last 5
        entries = store.list_entries()
        assert len(entries) == 5
        # Oldest entries should be removed
        assert entries[-1].event_id == "evt-5"

    def test_prune_removes_old_entries(self):
        """Test pruning entries before a cutoff."""
        store = InMemoryEventHistoryStore()
        old_time = datetime(2024, 1, 1, tzinfo=timezone.utc)
        new_time = datetime(2025, 1, 1, tzinfo=timezone.utc)
        store.record(
            EventHistoryEntry(
                event_id="evt-old", event_type="test", payload={}, source="test", timestamp=old_time
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-new", event_type="test", payload={}, source="test", timestamp=new_time
            )
        )

        deleted = store.prune(datetime(2024, 6, 1, tzinfo=timezone.utc))

        assert deleted == 1
        assert store.count() == 1
        assert store.get("evt-old") is None
        assert store.get("evt-new") is not None


class TestSQLiteEventHistoryStore:
    """Tests for SQLiteEventHistoryStore."""

    def test_record_and_get(self, tmp_path):
        store = SQLiteEventHistoryStore(db_path=str(tmp_path / "events.db"))
        entry = EventHistoryEntry(
            event_id="evt-1",
            event_type="test.event",
            payload={"a": 1},
            source="test",
            principal_id="user-1",
        )

        store.record(entry)
        retrieved = store.get("evt-1")

        assert retrieved is not None
        assert retrieved.event_id == "evt-1"
        assert retrieved.payload == {"a": 1}
        assert retrieved.principal_id == "user-1"

    def test_list_entries_filters(self, tmp_path):
        store = SQLiteEventHistoryStore(db_path=str(tmp_path / "events.db"))
        store.record(
            EventHistoryEntry(
                event_id="evt-1",
                event_type="reward.computed",
                payload={"run_id": "run-1"},
                source="events.rewards",
                tenant_id="tenant-a",
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-2",
                event_type="wallet.rewarded",
                payload={"run_id": "run-1"},
                source="events.learning",
                tenant_id="tenant-b",
            )
        )

        entries = store.list_entries(event_type="reward.computed", tenant_id="tenant-a")

        assert len(entries) == 1
        assert entries[0].event_id == "evt-1"

    def test_prune_removes_old_entries(self, tmp_path):
        store = SQLiteEventHistoryStore(db_path=str(tmp_path / "events.db"))
        store.record(
            EventHistoryEntry(
                event_id="evt-old",
                event_type="reward.computed",
                payload={},
                source="events.rewards",
                timestamp=datetime(2024, 1, 1, tzinfo=timezone.utc),
            )
        )
        store.record(
            EventHistoryEntry(
                event_id="evt-new",
                event_type="reward.computed",
                payload={},
                source="events.rewards",
                timestamp=datetime(2025, 1, 1, tzinfo=timezone.utc),
            )
        )

        deleted = store.prune(datetime(2024, 6, 1, tzinfo=timezone.utc))

        assert deleted == 1
        assert store.count() == 1
        assert store.get("evt-old") is None
        assert store.get("evt-new") is not None


class TestEventsRuntimeHistoryRetention:
    """Tests for runtime-level history retention loading."""

    def test_env_backend_preserves_file_retention_settings(self, tmp_path: Path, monkeypatch):
        """EVENTS_BACKEND should override only backend, not discard retention_days."""
        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            yaml.safe_dump(
                {
                    "event_store": {
                        "backend": "memory",
                        "retention_days": 14,
                        "db_path": str(tmp_path / "events.db"),
                    }
                }
            )
        )
        monkeypatch.setenv("EVENTS_BACKEND", "sqlite")

        runtime = EventsRuntime.from_config_dir(tmp_path)

        assert runtime.get_history_retention_days() == 14
        assert isinstance(runtime._history_store, SQLiteEventHistoryStore)

    def test_publish_prunes_stale_history_when_retention_is_due(self, tmp_path: Path):
        """Publishing should prune stale history entries once retention is configured."""
        settings_path = tmp_path / "settings.yaml"
        settings_path.write_text(
            yaml.safe_dump(
                {
                    "event_store": {
                        "backend": "memory",
                        "retention_days": 30,
                    }
                }
            )
        )
        runtime = EventsRuntime.from_config_dir(tmp_path)
        runtime._history_store.record(
            EventHistoryEntry(
                event_id="evt-old",
                event_type="reward.computed",
                payload={"run_id": "old-run"},
                source="events.rewards",
                timestamp=datetime.now(timezone.utc) - timedelta(days=45),
            )
        )
        runtime._history_store.record(
            EventHistoryEntry(
                event_id="evt-fresh",
                event_type="reward.computed",
                payload={"run_id": "fresh-run"},
                source="events.rewards",
                timestamp=datetime.now(timezone.utc) - timedelta(days=5),
            )
        )
        runtime._last_history_prune_at = datetime.now(timezone.utc) - timedelta(minutes=10)

        runtime.publish(
            event_type="reward.computed",
            payload={"run_id": "new-run"},
            source="events.rewards",
        )

        remaining_ids = {entry.event_id for entry in runtime.list_event_history(limit=10)}
        assert "evt-old" not in remaining_ids
        assert "evt-fresh" in remaining_ids
