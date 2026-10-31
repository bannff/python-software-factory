"""Redis event storage adapter.

Implements the EventStore Protocol from runtime/ports.py directly,
without inheriting from the deprecated base class.

Provides distributed event storage using Redis for pub/sub patterns.
Requires: redis package (optional dependency)
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any, List, Optional

from ..models import Event, EventFilter, EventQueryResult


class RedisEventStore:
    """Redis-backed event storage.
    
    Uses Redis for:
    - Event storage (hash per event)
    - Event listing (sorted set by timestamp)
    - Optional pub/sub for real-time distribution
    
    Configuration:
        url: Redis connection URL (redis://localhost:6379/0)
        key_prefix: Prefix for all keys (default: "events:")
        ttl_seconds: Optional TTL for events (default: None = no expiry)
    """

    def __init__(
        self,
        url: str = "redis://localhost:6379/0",
        key_prefix: str = "events:",
        ttl_seconds: int | None = None,
    ) -> None:
        self._url = url
        self._prefix = key_prefix
        self._ttl = ttl_seconds
        self._client: Any = None

    def _get_client(self) -> Any:
        """Lazy-load Redis client."""
        if self._client is None:
            try:
                import redis
                self._client = redis.from_url(self._url, decode_responses=True)
            except ImportError:
                raise RuntimeError(
                    "Redis package not installed. Install with: pip install redis"
                )
        return self._client

    def _event_key(self, event_id: str) -> str:
        return f"{self._prefix}event:{event_id}"

    def _index_key(self) -> str:
        return f"{self._prefix}index:timestamp"

    def _type_index_key(self, event_type: str) -> str:
        return f"{self._prefix}index:type:{event_type}"

    async def initialize(self) -> None:
        """Initialize Redis connection."""
        self._get_client().ping()

    def store(self, event: Event) -> str:
        """Store an event in Redis."""
        client = self._get_client()
        key = self._event_key(event.id)
        
        # Serialize event
        data = {
            "id": event.id,
            "type": event.type,
            "source": event.source,
            "payload": json.dumps(event.payload),
            "timestamp": event.timestamp.isoformat(),
            "trace_id": event.trace_id or "",
            "session_id": event.session_id or "",
            "principal_id": event.principal_id or "",
        }
        
        # Store event hash
        client.hset(key, mapping=data)
        if self._ttl:
            client.expire(key, self._ttl)
        
        # Add to timestamp index
        score = event.timestamp.timestamp()
        client.zadd(self._index_key(), {event.id: score})
        
        # Add to type index
        client.zadd(self._type_index_key(event.type), {event.id: score})
        
        return event.id

    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        client = self._get_client()
        key = self._event_key(event_id)
        data = client.hgetall(key)
        
        if not data:
            return None
        
        return Event(
            id=data["id"],
            type=data["type"],
            source=data["source"],
            payload=json.loads(data["payload"]),
            timestamp=datetime.fromisoformat(data["timestamp"]),
            trace_id=data.get("trace_id") or None,
            session_id=data.get("session_id") or None,
            principal_id=data.get("principal_id") or None,
        )

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> List[Event]:
        """List events with optional filters."""
        client = self._get_client()
        
        # Choose index based on filter
        if event_type:
            index_key = self._type_index_key(event_type)
        else:
            index_key = self._index_key()
        
        # Get event IDs from sorted set
        if descending:
            event_ids = client.zrevrange(index_key, offset, offset + limit - 1)
        else:
            event_ids = client.zrange(index_key, offset, offset + limit - 1)
        
        # Fetch events
        events = []
        for event_id in event_ids:
            event = self.get(event_id)
            if event:
                if source and event.source != source:
                    continue
                events.append(event)
        
        return events

    async def emit(self, event: Event) -> str:
        """Async emit (delegates to store)."""
        return self.store(event)

    async def query(self, filter: EventFilter) -> EventQueryResult:
        """Query events with filter."""
        events = self.list_events(
            event_type=filter.type,
            source=filter.source,
            limit=filter.limit,
            offset=filter.offset,
            descending=filter.descending,
        )
        return EventQueryResult(events=events)

    async def prune(self, before: datetime) -> int:
        """Remove events older than timestamp."""
        client = self._get_client()
        score = before.timestamp()
        
        # Get old event IDs
        old_ids = client.zrangebyscore(self._index_key(), "-inf", score)
        
        # Delete events and index entries
        for event_id in old_ids:
            event = self.get(event_id)
            if event:
                client.delete(self._event_key(event_id))
                client.zrem(self._type_index_key(event.type), event_id)
            client.zrem(self._index_key(), event_id)
        
        return len(old_ids)

    async def count(self) -> int:
        """Count total events."""
        client = self._get_client()
        return client.zcard(self._index_key())

    def health_check(self) -> dict[str, Any]:
        """Check Redis connectivity."""
        try:
            client = self._get_client()
            client.ping()
            count = client.zcard(self._index_key())
            return {"ok": True, "backend": "redis", "event_count": count}
        except Exception as e:
            return {"ok": False, "backend": "redis", "error": str(e)}
