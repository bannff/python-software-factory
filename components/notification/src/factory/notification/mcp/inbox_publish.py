"""Service-only trusted producer projection into the durable inbox.

``inbox_publish`` is callable ONLY by the in-process ``scheduler`` under an
exact ``projection`` operation binding (native caller-binding rail). It is not a
public create tool: a public or foreign caller/binding is rejected before the
handler runs. Ambient tenant+owner authority is re-checked against the bound
identity here; the runtime recomputes the content digest before any effect.
"""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import (
    ToolResult, get_envelope, operational, service_only,
)
from factory.mcp_utils.registration import typed_tool

from .contracts.inbox_publish import InboxPublishInput, InboxPublishOutput
from ..runtime.inbox_models import InboxAdapterError
from ..runtime.inbox_projection import (
    ProjectionConflictError, ProjectionDigestError, project_notification,
)

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime

_ERROR = "notification_projection_unavailable"


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register the scheduler-only durable inbox projection tool."""

    @typed_tool(mcp)
    @service_only(callers={"scheduler"}, binding="projection")
    @operational(input_model=InboxPublishInput, output_model=InboxPublishOutput)
    async def inbox_publish(
        tenant_id: str, owner_id: str, event_type: str, subject_id: str,
        revision: int, payload_digest: str, dedupe_key: str,
        priority: str = "critical", title: str = "", body: str = "",
    ) -> ToolResult[InboxPublishOutput]:
        """Persist a trusted schedule notification, then best-effort deliver."""
        parsed = InboxPublishInput.model_validate({
            "tenant_id": tenant_id, "owner_id": owner_id, "event_type": event_type,
            "subject_id": subject_id, "revision": revision,
            "payload_digest": payload_digest, "dedupe_key": dedupe_key,
            "priority": priority, "title": title, "body": body,
        })
        ambient = get_envelope() or {}
        if ambient.get("tenant_id") != parsed.tenant_id \
                or ambient.get("principal_id") != parsed.owner_id:
            return ToolResult(ok=False, error="notification_projection_authority_mismatch")
        try:
            outcome = await project_notification(
                runtime, tenant_id=parsed.tenant_id, owner_id=parsed.owner_id,
                event_type=parsed.event_type, subject_id=parsed.subject_id,
                revision=parsed.revision, payload_digest=parsed.payload_digest,
                dedupe_key=parsed.dedupe_key, priority=parsed.priority,
                title=parsed.title, body=parsed.body,
            )
        except ProjectionDigestError:
            return ToolResult(ok=False, error="notification_projection_digest_mismatch")
        except ProjectionConflictError:
            return ToolResult(ok=False, error="notification_projection_conflict")
        except (InboxAdapterError, ValueError):
            return ToolResult(ok=False, error=_ERROR)
        return ToolResult(ok=True, data=InboxPublishOutput(**outcome.model_dump()))


__all__ = ["register"]
