"""Shared fake for the WorkCompletedEmitterPlugin tests: a sync caller-bound
invoker over the events brick tools, mirroring the NativeEnvelopeInvoker
surface the plugin calls in production."""
from __future__ import annotations

from typing import Any


class EventsToolFake:
    """Records invoker calls; ``events_publish`` writes into an in-memory
    store that ``events_query_events`` reads back (idempotency realism)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.published: list[dict[str, Any]] = []

    def calls_for(self, tool_name: str) -> list[dict[str, Any]]:
        return [call for call in self.calls if call["tool"] == tool_name]

    @property
    def payloads(self) -> list[dict[str, Any]]:
        return [entry["payload"] for entry in self.published]

    def __call__(self, target: Any, *, arguments: dict[str, Any],
                 idempotency_key: str, envelope: dict[str, str] | None = None,
                 **__: Any) -> dict[str, Any]:
        self.calls.append({
            "tool": target.get("tool_name", ""), "arguments": dict(arguments),
            "idempotency_key": idempotency_key, "envelope": dict(envelope or {}),
        })
        if target.get("tool_name") == "events_query_events":
            hits = [
                entry for entry in self.published
                if entry["type"] == arguments.get("event_type") and str(
                    entry["payload"].get(arguments.get("payload_key"), ""),
                ) == arguments.get("payload_value")
            ][: int(arguments.get("limit", 100))]
            data: dict[str, Any] = {"events": hits}
        elif target.get("tool_name") == "events_publish":
            self.published.append({
                "type": arguments["event_type"], "payload": dict(arguments["payload"]),
            })
            data = {"event_id": "evt-1", "status": "published"}
        else:
            data = {}
        return {"result": {"structured_content": {
            "schema_version": "v1", "ok": True, "data": data, "error": None,
        }}}
