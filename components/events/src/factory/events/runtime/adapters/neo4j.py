"""Neo4j event storage adapter.

Stores events as :Event nodes with causal edges (CAUSED_BY).
Designed for event sourcing / audit trail — complements Redis pub/sub.
Requires: neo4j package (optional dependency)
"""

from __future__ import annotations

import importlib.util
import json
from datetime import datetime
from typing import Any, List, Optional

from ..models import Event, EventFilter, EventQueryResult

NEO4J_AVAILABLE = importlib.util.find_spec("neo4j") is not None


def _require_neo4j() -> None:
    if not NEO4J_AVAILABLE:
        raise ImportError("neo4j required. Install with: pip install neo4j")


class Neo4jEventStore:
    """Neo4j implementation of EventStore protocol.

    Events are stored as :Event nodes. Causal links are modeled as:
      (child)-[:CAUSED_BY]->(parent)  via trace_id correlation
      (event)-[:FROM_SOURCE]->(source_node)  for source grouping
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        auth: tuple[str, str] | None = None,
        database: str = "neo4j",
    ) -> None:
        _require_neo4j()
        import os
        from neo4j import GraphDatabase
        uri = uri or os.environ.get("NEO4J_URI", "bolt://localhost:7687")
        auth = auth or (
            os.environ.get("NEO4J_USER", "neo4j"),
            os.environ.get("NEO4J_PASSWORD", "password"),
        )
        self._driver = GraphDatabase.driver(uri, auth=auth)
        self._database = database
        self._uri = uri

    async def initialize(self) -> None:
        """Create indexes for efficient querying."""
        with self._driver.session(database=self._database) as s:
            for stmt in (
                "CREATE CONSTRAINT evt_id IF NOT EXISTS "
                "FOR (e:Event) REQUIRE e.id IS UNIQUE",
                "CREATE INDEX evt_type IF NOT EXISTS FOR (e:Event) ON (e.type)",
                "CREATE INDEX evt_ts IF NOT EXISTS FOR (e:Event) ON (e.timestamp)",
                "CREATE INDEX evt_source IF NOT EXISTS FOR (e:Event) ON (e.source)",
                "CREATE INDEX evt_trace IF NOT EXISTS FOR (e:Event) ON (e.trace_id)",
            ):
                try:
                    s.run(stmt)
                except Exception:
                    pass

    # -- sync ops --

    def store(self, event: Event) -> str:
        """Store an event as a :Event node, link via trace_id."""
        props = self._event_to_props(event)
        with self._driver.session(database=self._database) as s:
            s.run("CREATE (e:Event $props)", props=props)
            if event.trace_id:
                s.run(
                    "MATCH (child:Event {id: $id}), (parent:Event {trace_id: $tid}) "
                    "WHERE parent.id <> $id "
                    "WITH child, parent ORDER BY parent.timestamp DESC LIMIT 1 "
                    "MERGE (child)-[:CAUSED_BY]->(parent)",
                    id=event.id, tid=event.trace_id,
                )
        return event.id

    def get(self, event_id: str) -> Optional[Event]:
        """Get an event by ID."""
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (e:Event {id: $id}) RETURN e", id=event_id,
            ).single()
        if not rec:
            return None
        return self._node_to_event(dict(rec["e"]))

    def list_events(
        self,
        event_type: str | None = None,
        source: str | None = None,
        limit: int = 100,
        offset: int = 0,
        descending: bool = True,
    ) -> List[Event]:
        """List events with optional filters."""
        where: list[str] = []
        params: dict[str, Any] = {"lim": limit, "off": offset}
        if event_type:
            where.append("e.type = $etype")
            params["etype"] = event_type
        if source:
            where.append("e.source = $src")
            params["src"] = source
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        order = "DESC" if descending else "ASC"
        cypher = (
            f"MATCH (e:Event) {clause}"
            f"RETURN e ORDER BY e.timestamp {order} SKIP $off LIMIT $lim"
        )
        with self._driver.session(database=self._database) as s:
            return [self._node_to_event(dict(r["e"])) for r in s.run(cypher, **params)]

    # -- async ops --

    async def emit(self, event: Event) -> str:
        """Async emit delegates to sync store."""
        return self.store(event)

    async def query(self, filter: EventFilter) -> EventQueryResult:
        """Query events with advanced filtering."""
        where: list[str] = []
        params: dict[str, Any] = {"lim": filter.limit, "off": filter.offset}
        if filter.source:
            where.append("e.source = $src")
            params["src"] = filter.source
        if filter.type:
            where.append("e.type = $etype")
            params["etype"] = filter.type
        elif filter.type_prefix:
            where.append("e.type STARTS WITH $tp")
            params["tp"] = filter.type_prefix
        if filter.trace_id:
            where.append("e.trace_id = $tid")
            params["tid"] = filter.trace_id
        if filter.session_id:
            where.append("e.session_id = $sid")
            params["sid"] = filter.session_id
        if filter.start_time:
            where.append("e.timestamp >= $st")
            params["st"] = filter.start_time.isoformat()
        if filter.end_time:
            where.append("e.timestamp <= $et")
            params["et"] = filter.end_time.isoformat()
        clause = f"WHERE {' AND '.join(where)} " if where else ""
        order = "DESC" if filter.descending else "ASC"
        cypher = (
            f"MATCH (e:Event) {clause}"
            f"RETURN e ORDER BY e.timestamp {order} SKIP $off LIMIT $lim"
        )
        with self._driver.session(database=self._database) as s:
            events = [self._node_to_event(dict(r["e"])) for r in s.run(cypher, **params)]
        return EventQueryResult(events=events, total_count=len(events))

    async def prune(self, before: datetime) -> int:
        """Remove events older than timestamp."""
        with self._driver.session(database=self._database) as s:
            rec = s.run(
                "MATCH (e:Event) WHERE e.timestamp < $ts "
                "DETACH DELETE e RETURN count(e) AS c",
                ts=before.isoformat(),
            ).single()
        return rec["c"] if rec else 0

    async def count(self) -> int:
        """Count total events."""
        with self._driver.session(database=self._database) as s:
            rec = s.run("MATCH (e:Event) RETURN count(e) AS c").single()
        return rec["c"] if rec else 0

    # -- helpers --

    @staticmethod
    def _event_to_props(event: Event) -> dict[str, Any]:
        return {
            "id": event.id, "type": event.type, "source": event.source,
            "payload": json.dumps(event.payload),
            "timestamp": event.timestamp.isoformat(),
            "trace_id": event.trace_id or "",
            "session_id": event.session_id or "",
            "principal_id": event.principal_id or "",
        }

    @staticmethod
    def _node_to_event(node: dict[str, Any]) -> Event:
        return Event(
            id=node["id"], type=node["type"], source=node["source"],
            payload=json.loads(node.get("payload", "{}")),
            timestamp=datetime.fromisoformat(node["timestamp"]),
            trace_id=node.get("trace_id") or None,
            session_id=node.get("session_id") or None,
            principal_id=node.get("principal_id") or None,
        )
