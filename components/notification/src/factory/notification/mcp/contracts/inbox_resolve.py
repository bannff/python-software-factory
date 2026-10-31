"""Strict ingress/egress for the owner-scoped deep-link target resolver.

Ingress derives tenant/owner from the ambient envelope, so only the
notification id appears (no tenant/owner field). Egress returns the existing
closed :class:`NotificationTarget` union plus an ``authorized`` flag — never a
URL, route, tenant/owner field, or any source payload. The frontend maps the
closed ``(kind, id)`` to internal navigation.
"""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from ...runtime.inbox_targets import NotificationTarget
from .inbox_inputs import NOTIFICATION_ID_PATTERN
from .inputs import NotificationDTO


class InboxResolveInput(NotificationDTO):
    notification_id: str = Field(pattern=NOTIFICATION_ID_PATTERN)


class InboxResolveOutput(NotificationDTO):
    authorized: Literal[True] = True
    target: NotificationTarget


__all__ = ["InboxResolveInput", "InboxResolveOutput"]
