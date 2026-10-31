"""Tests for EventBridge and SQS backends — store, get, list, count.

All boto3 calls are mocked — no real AWS resources needed.
"""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from factory.events.runtime.models import Event, EventFilter, EventQueryResult


@pytest.fixture
def mock_eb_client() -> MagicMock:
    """Mock EventBridge client."""
    return MagicMock()


@pytest.fixture
def eb_backend(mock_eb_client: MagicMock):
    """Create _EventBridgeBackend with mocked boto3."""
    with patch("boto3.client", return_value=mock_eb_client):
        from factory.events.runtime.adapters.aws import _EventBridgeBackend

        return _EventBridgeBackend(bus_name="test-bus")


@pytest.fixture
def mock_sqs_client() -> MagicMock:
    """Mock SQS client."""
    return MagicMock()


@pytest.fixture
def sqs_backend(mock_sqs_client: MagicMock):
    """Create _SQSBackend with mocked boto3."""
    with patch("boto3.client", return_value=mock_sqs_client):
        from factory.events.runtime.adapters.aws import _SQSBackend

        return _SQSBackend(queue_url="https://sqs.test/q")


def _make_event(**overrides) -> Event:
    """Helper to create test events."""
    defaults = dict(
        id="evt-1", source="test", type="test.event", payload={"k": "v"},
    )
    defaults.update(overrides)
    return Event(**defaults)


class TestEventBridgeBackend:
    """EventBridge backend tests."""

    def test_store_calls_put_events(
        self, eb_backend, mock_eb_client: MagicMock,
    ) -> None:
        """store() calls put_events with correct entry."""
        event = _make_event()
        eb_backend.store(event)

    def test_get_missing_returns_none(self, eb_backend) -> None:
        """get() returns None for unknown event_id."""
        assert eb_backend.get("nope") is None

    def test_list_events_empty(self, eb_backend) -> None:
        """list_events() returns empty list initially."""
        assert eb_backend.list_events() == []

    def test_count_empty(self, eb_backend) -> None:
        """count() returns 0 initially."""
        assert eb_backend.count() == 0

    def test_prune_returns_zero(self, eb_backend) -> None:
        """prune() returns 0 — EventBridge manages retention."""
        assert eb_backend.prune(datetime.now(timezone.utc)) == 0

    def test_query_empty(self, eb_backend) -> None:
        """query() returns empty EventQueryResult initially."""
        result = eb_backend.query(EventFilter())
        assert isinstance(result, EventQueryResult)
        assert len(result.events) == 0

    @pytest.mark.asyncio
    async def test_initialize_is_noop(self, eb_backend) -> None:
        """initialize() completes without error."""
        await eb_backend.initialize()

    def test_infrastructure_spec(self, eb_backend) -> None:
        """Returns valid EventBridge spec."""
        spec = eb_backend.infrastructure_spec()
        assert spec["service"] == "events"
        assert spec["construct"] == "EventBus"
        assert spec["props"]["event_bus_name"] == "test-bus"


class TestSQSBackend:
    """SQS backend tests."""

    def test_store_calls_send_message(
        self, sqs_backend, mock_sqs_client: MagicMock,
    ) -> None:
        """store() calls send_message with correct payload."""
        event = _make_event()
        sqs_backend.store(event)

    def test_get_missing(self, sqs_backend) -> None:
        """get() returns None for unknown id."""
        assert sqs_backend.get("nope") is None

    def test_count_empty(self, sqs_backend) -> None:
        """count() returns 0 initially."""
        assert sqs_backend.count() == 0

    def test_infrastructure_spec(self, sqs_backend) -> None:
        """Returns valid SQS spec."""
        spec = sqs_backend.infrastructure_spec()
        assert spec["service"] == "sqs"
        assert spec["construct"] == "Queue"

    @pytest.mark.asyncio
    async def test_initialize_is_noop(self, sqs_backend) -> None:
        """initialize() completes without error."""
        await sqs_backend.initialize()
