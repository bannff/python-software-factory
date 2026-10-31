"""Tests for subscription registry."""

import pytest

from factory.events.runtime.subscriptions import (
    SubscriptionDefinition,
    SubscriptionRegistry,
)


class TestSubscriptionDefinition:
    """Tests for SubscriptionDefinition model."""

    def test_create_subscription(self):
        """Test creating a subscription definition."""
        sub = SubscriptionDefinition(
            id="sub-1",
            event_type="user.created",
            handler="notify_admin",
            description="Notify admin on user creation",
        )
        assert sub.id == "sub-1"
        assert sub.event_type == "user.created"
        assert sub.handler == "notify_admin"
        assert sub.enabled is True

    def test_subscription_with_filters(self):
        """Test subscription with filters."""
        sub = SubscriptionDefinition(
            id="sub-2",
            event_type="order.*",
            handler="process_order",
            filters={"status": "pending"},
        )
        assert sub.filters == {"status": "pending"}

    def test_disabled_subscription(self):
        """Test disabled subscription."""
        sub = SubscriptionDefinition(
            id="sub-3",
            event_type="test.event",
            handler="test_handler",
            enabled=False,
        )
        assert sub.enabled is False


class TestSubscriptionRegistry:
    """Tests for SubscriptionRegistry."""

    def test_register_subscription(self):
        """Test registering a subscription."""
        registry = SubscriptionRegistry()
        sub = SubscriptionDefinition(
            id="sub-1",
            event_type="user.created",
            handler="notify_admin",
        )
        registry.register(sub)
        assert registry.get("sub-1") == sub

    def test_unregister_subscription(self):
        """Test unregistering a subscription."""
        registry = SubscriptionRegistry()
        sub = SubscriptionDefinition(
            id="sub-1",
            event_type="user.created",
            handler="notify_admin",
        )
        registry.register(sub)
        registry.unregister("sub-1")
        assert registry.get("sub-1") is None

    def test_list_all_subscriptions(self):
        """Test listing all subscriptions."""
        registry = SubscriptionRegistry()
        sub1 = SubscriptionDefinition(
            id="sub-1", event_type="user.created", handler="h1"
        )
        sub2 = SubscriptionDefinition(
            id="sub-2", event_type="order.placed", handler="h2"
        )
        registry.register(sub1)
        registry.register(sub2)
        all_subs = registry.list_all()
        assert len(all_subs) == 2

    def test_find_by_event_type(self):
        """Test finding subscriptions by event type."""
        registry = SubscriptionRegistry()
        sub1 = SubscriptionDefinition(
            id="sub-1", event_type="user.created", handler="h1"
        )
        sub2 = SubscriptionDefinition(
            id="sub-2", event_type="user.updated", handler="h2"
        )
        sub3 = SubscriptionDefinition(
            id="sub-3", event_type="order.placed", handler="h3"
        )
        registry.register(sub1)
        registry.register(sub2)
        registry.register(sub3)

        user_subs = registry.find_by_event_type("user.created")
        assert len(user_subs) == 1
        assert user_subs[0].id == "sub-1"

    def test_find_by_pattern(self):
        """Test finding subscriptions by pattern."""
        registry = SubscriptionRegistry()
        sub1 = SubscriptionDefinition(id="sub-1", event_type="user.*", handler="h1")
        sub2 = SubscriptionDefinition(id="sub-2", event_type="order.*", handler="h2")
        registry.register(sub1)
        registry.register(sub2)

        # Exact match for pattern
        matches = registry.find_matching("user.created")
        assert len(matches) == 1
        assert matches[0].id == "sub-1"

    def test_enabled_only_filter(self):
        """Test filtering enabled subscriptions only."""
        registry = SubscriptionRegistry()
        sub1 = SubscriptionDefinition(
            id="sub-1", event_type="test", handler="h1", enabled=True
        )
        sub2 = SubscriptionDefinition(
            id="sub-2", event_type="test", handler="h2", enabled=False
        )
        registry.register(sub1)
        registry.register(sub2)

        enabled = registry.list_all(enabled_only=True)
        assert len(enabled) == 1
        assert enabled[0].id == "sub-1"
