"""Tests for AWS event store adapter — service selector and delegation.

All boto3 calls are mocked — no real AWS resources needed.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from factory.events.runtime.models import Event, EventFilter, EventQueryResult


class TestAWSEventStoreSelector:
    """Service selector: eventbridge vs sqs vs invalid."""

    @patch("boto3.client")
    def test_eventbridge_service(self, mock_client: MagicMock) -> None:
        """service='eventbridge' creates EventBridge backend."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        store = AWSEventStore(service="eventbridge")
        assert store._service == "eventbridge"

    @patch("boto3.client")
    def test_sqs_service(self, mock_client: MagicMock) -> None:
        """service='sqs' creates SQS backend."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        store = AWSEventStore(service="sqs")
        assert store._service == "sqs"

    def test_invalid_service_raises(self) -> None:
        """Unknown service raises ValueError."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        with pytest.raises(ValueError, match="Unknown AWS events service"):
            AWSEventStore(service="kinesis")

    @patch("boto3.client")
    def test_default_service_is_eventbridge(self, mock_client: MagicMock) -> None:
        """Default service is eventbridge."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        store = AWSEventStore()
        assert store._service == "eventbridge"


class TestAWSEventStoreInfraSpec:
    """infrastructure_spec() for each backend."""

    @patch("boto3.client")
    def test_eventbridge_spec(self, mock_client: MagicMock) -> None:
        """EventBridge backend returns valid spec."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        store = AWSEventStore(service="eventbridge", bus_name="my-bus")
        spec = store.infrastructure_spec()
        assert spec["service"] == "events"
        assert spec["construct"] == "EventBus"
        assert spec["props"]["event_bus_name"] == "my-bus"

    @patch("boto3.client")
    def test_sqs_spec(self, mock_client: MagicMock) -> None:
        """SQS backend returns valid spec."""
        from factory.events.runtime.adapters.aws import AWSEventStore

        store = AWSEventStore(service="sqs")
        spec = store.infrastructure_spec()
        assert spec["service"] == "sqs"
        assert spec["construct"] == "Queue"
