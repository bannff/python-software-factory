"""Tests for delivery tracking."""
from __future__ import annotations

import pytest
from datetime import datetime

from factory.notification.runtime.delivery import DeliveryStore, InMemoryDeliveryStore
from factory.notification.runtime.models import DeliveryStatus


class TestInMemoryDeliveryStore:
    """Test in-memory delivery store."""

    def test_save_and_get(self) -> None:
        """Should save and retrieve delivery status."""
        store = InMemoryDeliveryStore()
        
        status = DeliveryStatus(
            message_id="msg-123",
            status="sent",
            backend="stdio",
            recipient="test@example.com",
        )
        
        store.save(status)
        retrieved = store.get("msg-123")
        
        assert retrieved is not None
        assert retrieved.message_id == "msg-123"
        assert retrieved.status == "sent"
        assert retrieved.recipient == "test@example.com"

    def test_get_nonexistent(self) -> None:
        """Should return None for nonexistent message."""
        store = InMemoryDeliveryStore()
        
        result = store.get("nonexistent")
        assert result is None

    def test_list_all(self) -> None:
        """Should list all deliveries."""
        store = InMemoryDeliveryStore()
        
        for i in range(3):
            store.save(DeliveryStatus(
                message_id=f"msg-{i}",
                status="sent",
                backend="stdio",
                recipient=f"user{i}@example.com",
            ))
        
        deliveries = store.list()
        assert len(deliveries) == 3

    def test_list_with_status_filter(self) -> None:
        """Should filter by status."""
        store = InMemoryDeliveryStore()
        
        store.save(DeliveryStatus(message_id="msg-1", status="sent", backend="stdio", recipient="a@x.com"))
        store.save(DeliveryStatus(message_id="msg-2", status="failed", backend="stdio", recipient="b@x.com"))
        store.save(DeliveryStatus(message_id="msg-3", status="sent", backend="stdio", recipient="c@x.com"))
        
        sent = store.list(status="sent")
        assert len(sent) == 2
        
        failed = store.list(status="failed")
        assert len(failed) == 1

    def test_list_with_limit(self) -> None:
        """Should respect limit parameter."""
        store = InMemoryDeliveryStore()
        
        for i in range(10):
            store.save(DeliveryStatus(
                message_id=f"msg-{i}",
                status="sent",
                backend="stdio",
                recipient=f"user{i}@example.com",
            ))
        
        deliveries = store.list(limit=5)
        assert len(deliveries) == 5

    def test_update_status(self) -> None:
        """Should update existing delivery status."""
        store = InMemoryDeliveryStore()
        
        store.save(DeliveryStatus(
            message_id="msg-123",
            status="queued",
            backend="celery",
            recipient="test@example.com",
        ))
        
        # Update to sent
        store.save(DeliveryStatus(
            message_id="msg-123",
            status="sent",
            backend="celery",
            recipient="test@example.com",
        ))
        
        retrieved = store.get("msg-123")
        assert retrieved.status == "sent"
