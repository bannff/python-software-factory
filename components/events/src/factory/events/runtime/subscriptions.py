"""Subscription registry for event handlers."""

from __future__ import annotations

import fnmatch
from typing import Any

from pydantic import BaseModel, Field


class SubscriptionDefinition(BaseModel):
    """Definition of an event subscription."""

    id: str = Field(..., description="Unique subscription identifier")
    event_type: str = Field(
        ...,
        description="Event type pattern to subscribe to (supports wildcards)",
    )
    handler: str = Field(..., description="Handler identifier to invoke")
    description: str | None = Field(
        default=None,
        description="Human-readable description",
    )
    filters: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional filters for event matching",
    )
    enabled: bool = Field(
        default=True,
        description="Whether the subscription is active",
    )
    priority: int = Field(
        default=0,
        description="Priority for ordering (higher = first)",
    )

    model_config = {"extra": "forbid"}


class SubscriptionRegistry:
    """Registry for managing event subscriptions."""

    def __init__(self) -> None:
        self._subscriptions: dict[str, SubscriptionDefinition] = {}

    def register(self, subscription: SubscriptionDefinition) -> None:
        """Register a subscription."""
        self._subscriptions[subscription.id] = subscription

    def unregister(self, subscription_id: str) -> bool:
        """Unregister a subscription by ID."""
        if subscription_id in self._subscriptions:
            del self._subscriptions[subscription_id]
            return True
        return False

    def get(self, subscription_id: str) -> SubscriptionDefinition | None:
        """Get a subscription by ID."""
        return self._subscriptions.get(subscription_id)

    def list_all(self, enabled_only: bool = False) -> list[SubscriptionDefinition]:
        """List all subscriptions."""
        subs = list(self._subscriptions.values())
        if enabled_only:
            subs = [s for s in subs if s.enabled]
        return sorted(subs, key=lambda s: (-s.priority, s.id))

    def find_by_event_type(self, event_type: str) -> list[SubscriptionDefinition]:
        """Find subscriptions by exact event type."""
        return [
            s
            for s in self._subscriptions.values()
            if s.event_type == event_type and s.enabled
        ]

    def find_matching(self, event_type: str) -> list[SubscriptionDefinition]:
        """Find subscriptions matching an event type (supports wildcards)."""
        matches = []
        for sub in self._subscriptions.values():
            if not sub.enabled:
                continue
            # Support wildcards like "user.*" matching "user.created"
            if fnmatch.fnmatch(event_type, sub.event_type):
                matches.append(sub)
            elif fnmatch.fnmatch(sub.event_type, event_type):
                matches.append(sub)
            elif sub.event_type == event_type:
                matches.append(sub)
        return sorted(matches, key=lambda s: (-s.priority, s.id))

    def clear(self) -> None:
        """Clear all subscriptions."""
        self._subscriptions.clear()
