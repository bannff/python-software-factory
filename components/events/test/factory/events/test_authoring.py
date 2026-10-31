"""Tests for authoring security."""

import os
import tempfile
from pathlib import Path

import pytest

from factory.events.authoring import EventsAuthoring


class TestAuthoringDisabledByDefault:
    """Tests that authoring is disabled by default."""

    def test_authoring_disabled_by_default(self, tmp_path):
        """Test authoring is disabled when env var not set."""
        # Ensure env var is not set
        os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)

        authoring = EventsAuthoring(tmp_path)
        assert authoring.is_enabled() is False

    def test_authoring_enabled_with_env_var(self, tmp_path):
        """Test authoring is enabled with env var."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            assert authoring.is_enabled() is True
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)


class TestAuthoringPathScoping:
    """Tests for path scoping security."""

    def test_rejects_path_traversal(self, tmp_path):
        """Test that path traversal is rejected."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            result = authoring.upsert_subscription(
                "../../../etc/passwd",
                {"id": "test", "event_type": "test", "handler": "test"},
            )
            assert result["ok"] is False
            assert (
                "traversal" in result["error"].lower()
                or "invalid" in result["error"].lower()
            )
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)

    def test_rejects_absolute_path(self, tmp_path):
        """Test that absolute paths are rejected."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            result = authoring.upsert_subscription(
                "/etc/passwd",
                {"id": "test", "event_type": "test", "handler": "test"},
            )
            assert result["ok"] is False
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)


class TestAuthoringOperations:
    """Tests for authoring operations when enabled."""

    def test_upsert_subscription(self, tmp_path):
        """Test upserting a subscription."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            result = authoring.upsert_subscription(
                "test-sub",
                {
                    "id": "test-sub",
                    "event_type": "user.created",
                    "handler": "notify_admin",
                },
            )
            assert result["ok"] is True
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)

    def test_delete_subscription(self, tmp_path):
        """Test deleting a subscription."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            # First create
            authoring.upsert_subscription(
                "test-sub",
                {
                    "id": "test-sub",
                    "event_type": "user.created",
                    "handler": "notify_admin",
                },
            )
            # Then delete
            result = authoring.delete_subscription("test-sub")
            assert result["ok"] is True
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)

    def test_validate_subscriptions(self, tmp_path):
        """Test validating subscriptions."""
        os.environ["EVENTS_ENABLE_AUTHORING_TOOLS"] = "1"
        try:
            authoring = EventsAuthoring(tmp_path)
            result = authoring.validate_subscriptions()
            assert "valid" in result or "errors" in result
        finally:
            os.environ.pop("EVENTS_ENABLE_AUTHORING_TOOLS", None)
