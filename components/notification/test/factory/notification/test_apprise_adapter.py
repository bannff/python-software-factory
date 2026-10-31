"""Tests for AppriseBackend adapter (apprise library).

Tests instantiation and protocol conformance. Network calls are
mocked since apprise would try to reach real services.
"""

from __future__ import annotations

import pytest
from unittest.mock import patch, MagicMock

from factory.notification.runtime.backends.apprise_adapter import AppriseBackend
from factory.notification.runtime.models import NotificationRequest


class TestAppriseBackend:
    """Tests for AppriseBackend using real apprise library."""

    def test_import(self) -> None:
        """AppriseBackend and apprise are importable."""
        import apprise
        assert apprise.Apprise is not None
        assert AppriseBackend is not None

    def test_name(self) -> None:
        """Backend name is 'apprise'."""
        backend = AppriseBackend()
        assert backend.name == "apprise"

    @pytest.mark.asyncio
    async def test_health_check_before_init(self) -> None:
        """health_check returns False before initialization."""
        backend = AppriseBackend()
        assert await backend.health_check() is False

    @pytest.mark.asyncio
    async def test_initialize_with_urls(self) -> None:
        """initialize() configures apprise with service URLs."""
        backend = AppriseBackend()
        await backend.initialize({"urls": ["json://localhost"]})
        assert await backend.health_check() is True

    @pytest.mark.asyncio
    async def test_initialize_empty_urls(self) -> None:
        """initialize() with no URLs means unhealthy."""
        backend = AppriseBackend()
        await backend.initialize({"urls": []})
        assert await backend.health_check() is False

    @pytest.mark.asyncio
    async def test_send_before_init(self) -> None:
        """send() before init returns failed status."""
        backend = AppriseBackend()
        request = NotificationRequest(
            recipient="user@example.com", content="hello", subject="Test",
        )
        result = await backend.send(request)
        assert result.status == "failed"
        assert "not initialized" in result.error.lower()

    @pytest.mark.asyncio
    async def test_send_success(self) -> None:
        """send() returns 'sent' when apprise.notify succeeds."""
        backend = AppriseBackend()
        await backend.initialize({"urls": ["json://localhost"]})

        with patch.object(backend._ap, "notify", return_value=True):
            request = NotificationRequest(
                recipient="user@example.com", content="Hello world", subject="Greetings",
            )
            result = await backend.send(request)
            assert result.status == "sent"
            assert result.backend == "apprise"
            assert result.message_id is not None

    @pytest.mark.asyncio
    async def test_send_failure(self) -> None:
        """send() returns 'failed' when apprise.notify fails."""
        backend = AppriseBackend()
        await backend.initialize({"urls": ["json://localhost"]})

        with patch.object(backend._ap, "notify", return_value=False):
            request = NotificationRequest(
                recipient="user@example.com", content="Hello", subject="Test",
            )
            result = await backend.send(request)
            assert result.status == "failed"
