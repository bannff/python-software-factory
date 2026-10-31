"""Typed operational MCP tools for Events."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import (
    ToolResult, build_event_publish_input, get_envelope, make_serializable, operational,
)

from . import operational_history
from .dev_loop import register as register_dev_loop
from .learning_signal import register as register_learning_signal
from .projection import PROTECTED_EVENT_TYPES, register as register_projection
from .contracts.operational import (
    EventIdInput, GetEventOutput, ListEventsInput, ListEventsOutput, PublishInput,
    PublishOutput, ReplayInput, ReplayOutput,
)
from ..runtime.envelope import ContextEnvelope

if TYPE_CHECKING:
    from ..runtime.runtime import EventsRuntime


def _canonical_event_context(
    payload: dict[str, object], source_context: dict[str, object], *,
    authoritative_run_id: object | None = None,
) -> tuple[dict[str, object], ContextEnvelope]:
    """Build an Events envelope with optional durable Workflow run authority."""
    canonical = build_event_publish_input(
        payload, source_context, authoritative_run_id=authoritative_run_id,
    )
    ambient = get_envelope() or {}
    attributes: dict[str, object] = {}
    for values in (source_context.get("attributes"), ambient.get("attributes")):
        if isinstance(values, dict):
            attributes.update(values)
    attributes.update(canonical.get("attributes", {}))
    envelope = ContextEnvelope(
        tenant_id=canonical.get("tenant_id"),
        principal_id=canonical.get("principal_id"),
        session_id=canonical.get("session_id"),
        request_id=canonical.get("request_id"),
        attributes=attributes,
    )
    return canonical, envelope


def register(mcp: Any, get_runtime: Callable[[], "EventsRuntime"]) -> None:
    """Register operational tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=PublishInput, output_model=PublishOutput)
    def events_publish(event_type: str, payload: dict[str, object], source: str,
                       tenant_id: str | None = None, principal_id: str | None = None,
                       session_id: str | None = None, request_id: str | None = None,
                       attributes: dict[str, object] | None = None,
                       run_id_authoritative: bool = False) -> ToolResult[PublishOutput]:
        if event_type in PROTECTED_EVENT_TYPES:
            return ToolResult(ok=False, error="protected_event_requires_service")
        source_context = {
            "tenant_id": tenant_id, "principal_id": principal_id,
            "session_id": session_id, "request_id": request_id,
            "attributes": attributes or {},
        }
        authority = payload.get("run_id") if run_id_authoritative else None
        canonical, envelope = _canonical_event_context(
            payload, source_context, authoritative_run_id=authority,
        )
        result = get_runtime().publish(
            event_type=event_type, payload=canonical["payload"], source=source,
            envelope=envelope,
        )
        return {"event_id": result.event_id, "status": result.status,
                "subscriptions_matched": result.subscriptions_matched,
                "subscriptions_dispatched": result.subscriptions_dispatched,
                "timestamp": str(result.timestamp)}

    @mcp.tool()
    @operational(input_model=EventIdInput, output_model=GetEventOutput)
    def events_get_event(event_id: str) -> ToolResult[GetEventOutput]:
        event = get_runtime().get_event(event_id)
        if event is None:
            return {"found": False, "error": "Event not found"}
        return {"found": True, "event": make_serializable({"id": event.id, "type": event.type,
            "payload": event.payload, "source": event.source,
            "timestamp": event.timestamp.isoformat()})}

    @mcp.tool()
    @operational(input_model=ListEventsInput, output_model=ListEventsOutput)
    def events_list_events(event_type: str | None = None, source: str | None = None,
                           limit: int = 100) -> ToolResult[ListEventsOutput]:
        events = get_runtime().list_events(event_type=event_type, source=source, limit=limit)
        rows = [{"id": event.id, "type": event.type, "payload": event.payload,
                 "source": event.source, "timestamp": event.timestamp.isoformat()}
                for event in events]
        return {"events": make_serializable(rows), "total": len(rows)}

    @mcp.tool()
    @operational(input_model=ReplayInput, output_model=ReplayOutput)
    def events_replay(event_id: str, tenant_id: str | None = None,
                      principal_id: str | None = None, session_id: str | None = None,
                      request_id: str | None = None,
                      attributes: dict[str, object] | None = None) -> ToolResult[ReplayOutput]:
        source_context = {
            "tenant_id": tenant_id, "principal_id": principal_id,
            "session_id": session_id, "request_id": request_id,
            "attributes": attributes or {},
        }
        _, envelope = _canonical_event_context({}, source_context)
        result = get_runtime().replay_event(event_id, envelope)
        if result is None:
            return {"ok": False, "error": "Event not found in history"}
        return {"ok": True, "new_event_id": result.event_id, "status": result.status,
                "subscriptions_matched": result.subscriptions_matched}

    operational_history.register(mcp, get_runtime)
    register_projection(mcp, get_runtime)
    register_learning_signal(mcp, get_runtime)
    register_dev_loop(mcp, get_runtime)
