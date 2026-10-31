"""AWS adapter for events brick.

Supports EventBridge (event bus) and SQS (message queue).
Service is selected at init time via the `service` parameter.
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from typing import Any, Optional

from factory.events.runtime.models import Event, EventFilter, EventQueryResult


def _require_boto3() -> None:
    try:
        import boto3  # noqa: F401
    except ImportError:
        msg = "pip install boto3 — required for AWS events adapter"
        raise ImportError(msg)


class AWSEventStore:
    """AWS adapter — delegates to EventBridge or SQS backend."""

    def __init__(self, service: str = "eventbridge", **config: Any) -> None:
        _require_boto3()
        self._service = service
        self._config = config
        match service:
            case "eventbridge":
                self._backend = _EventBridgeBackend(**config)
            case "sqs":
                self._backend = _SQSBackend(**config)
            case _:
                raise ValueError(f"Unknown AWS events service: {service}")

    async def initialize(self) -> None:
        await self._backend.initialize()

    def store(self, event: Event) -> str:
        return self._backend.store(event)

    def get(self, event_id: str) -> Optional[Event]:
        return self._backend.get(event_id)

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> list[Event]:
        return self._backend.list_events(
            event_type, source, limit, offset, descending,
        )

    async def emit(self, event: Event) -> str:
        return self._backend.store(event)

    async def query(self, filter: EventFilter) -> EventQueryResult:
        return self._backend.query(filter)

    async def prune(self, before: datetime) -> int:
        return self._backend.prune(before)

    async def count(self) -> int:
        return self._backend.count()

    def infrastructure_spec(self) -> dict[str, Any]:
        """Return AWS resource requirements for this adapter."""
        return self._backend.infrastructure_spec()


class _EventBridgeBackend:
    """EventBridge backend for event bus pattern."""

    def __init__(
        self,
        bus_name: str = "factory-events",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        import boto3

        self._bus_name = bus_name
        self._client = boto3.client("events", region_name=region)
        self._local: dict[str, Event] = {}  # local index for get()

    async def initialize(self) -> None:
        pass

    def store(self, event: Event) -> str:
        event_id = event.id or str(uuid.uuid4())
        self._client.put_events(
            Entries=[{
                "Source": event.source or "factory",
                "DetailType": event.type,
                "Detail": json.dumps(event.payload or {}),
                "EventBusName": self._bus_name,
            }],
        )
        self._local[event_id] = event
        return event_id

    def get(self, event_id: str) -> Optional[Event]:
        return self._local.get(event_id)

    def list_events(self, *args: Any, **kwargs: Any) -> list[Event]:
        return list(self._local.values())

    def query(self, filter: EventFilter) -> EventQueryResult:
        events = list(self._local.values())
        return EventQueryResult(events=events, total_count=len(events))

    def prune(self, before: datetime) -> int:
        return 0  # EventBridge manages retention

    def count(self) -> int:
        return len(self._local)

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "events",
            "construct": "EventBus",
            "props": {"event_bus_name": self._bus_name},
        }


class _SQSBackend:
    """SQS backend for message queue pattern."""

    def __init__(
        self,
        queue_url: str = "",
        region: str = "us-east-1",
        **kwargs: Any,
    ) -> None:
        import boto3

        self._queue_url = queue_url
        self._client = boto3.client("sqs", region_name=region)
        self._local: dict[str, Event] = {}

    async def initialize(self) -> None:
        pass

    def store(self, event: Event) -> str:
        event_id = event.id or str(uuid.uuid4())
        self._client.send_message(
            QueueUrl=self._queue_url,
            MessageBody=json.dumps({
                "id": event_id,
                "type": event.type,
                "data": event.payload or {},
            }),
        )
        self._local[event_id] = event
        return event_id

    def get(self, event_id: str) -> Optional[Event]:
        return self._local.get(event_id)

    def list_events(self, *args: Any, **kwargs: Any) -> list[Event]:
        return list(self._local.values())

    def query(self, filter: EventFilter) -> EventQueryResult:
        events = list(self._local.values())
        return EventQueryResult(events=events, total_count=len(events))

    def prune(self, before: datetime) -> int:
        return 0

    def count(self) -> int:
        return len(self._local)

    def infrastructure_spec(self) -> dict[str, Any]:
        return {
            "service": "sqs",
            "construct": "Queue",
            "props": {"queue_name": "factory-events"},
        }
