"""Closed, discriminated deep-link target union for the notification inbox.

Each target carries only its canonical bounded ID — never a URL or filesystem
path (M7 "Targets are a closed union ... arbitrary/external URLs are
forbidden"). The frontend resolves an ID to an internal route; opening a target
rechecks ambient authority against its source brick, so an inbox ID grants no
access on its own. The canonical-ID alphabet forbids slashes, whitespace, and
scheme punctuation, which structurally rejects ``http://…``, ``/etc/passwd``,
and ``../escape`` at ingress.
"""
from __future__ import annotations

import re
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

# Ambient authority identity — mirrors Migration/Session/Crew ``Identity``.
Identity = Annotated[
    str, Field(min_length=1, max_length=256, pattern=r"^[^\x00-\x1f\x7f]+$")
]

# Canonical ID: no slash, no whitespace, no scheme/query punctuation. Colons are
# permitted (digest-style run ids) but ``://`` cannot form without slashes.
_CANONICAL_ID = r"^[A-Za-z0-9][A-Za-z0-9_.:=+-]{0,255}$"
CanonicalId = Annotated[str, Field(pattern=_CANONICAL_ID)]

_ID_RE = re.compile(_CANONICAL_ID)


class _TargetBase(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class SessionTarget(_TargetBase):
    kind: Literal["session"] = "session"
    session_id: CanonicalId


class WorkflowRunTarget(_TargetBase):
    kind: Literal["workflow_run"] = "workflow_run"
    run_id: CanonicalId


class ScheduleTarget(_TargetBase):
    kind: Literal["schedule"] = "schedule"
    schedule_id: CanonicalId


class ArtifactTarget(_TargetBase):
    kind: Literal["artifact"] = "artifact"
    slug: CanonicalId


class CrewTarget(_TargetBase):
    kind: Literal["crew"] = "crew"
    crew_id: CanonicalId


class LessonTarget(_TargetBase):
    kind: Literal["lesson"] = "lesson"
    lesson_id: CanonicalId


class CanvasTarget(_TargetBase):
    kind: Literal["canvas"] = "canvas"
    view_id: CanonicalId


NotificationTarget = Annotated[
    Union[
        SessionTarget, WorkflowRunTarget, ScheduleTarget, ArtifactTarget,
        CrewTarget, LessonTarget, CanvasTarget,
    ],
    Field(discriminator="kind"),
]

# The single ID field name each variant exposes, keyed by discriminator.
_ID_FIELD: dict[str, str] = {
    "session": "session_id", "workflow_run": "run_id", "schedule": "schedule_id",
    "artifact": "slug", "crew": "crew_id", "lesson": "lesson_id",
    "canvas": "view_id",
}
_BY_KIND: dict[str, type[_TargetBase]] = {
    "session": SessionTarget, "workflow_run": WorkflowRunTarget,
    "schedule": ScheduleTarget, "artifact": ArtifactTarget, "crew": CrewTarget,
    "lesson": LessonTarget, "canvas": CanvasTarget,
}


def target_kind(target: _TargetBase) -> str:
    """The discriminator value of a built target."""
    return target.kind  # type: ignore[attr-defined]


def target_id(target: _TargetBase) -> str:
    """The single canonical ID a target carries."""
    return getattr(target, _ID_FIELD[target.kind])  # type: ignore[attr-defined]


def build_target(kind: str, ident: str) -> _TargetBase:
    """Reconstruct the exact variant for a persisted ``(kind, id)`` pair."""
    model = _BY_KIND.get(kind)
    if model is None:
        raise ValueError("unknown notification target kind")
    return model(**{_ID_FIELD[kind]: ident})


__all__ = [
    "ArtifactTarget", "CanonicalId", "CanvasTarget", "CrewTarget", "Identity",
    "LessonTarget", "NotificationTarget", "ScheduleTarget", "SessionTarget",
    "WorkflowRunTarget", "build_target", "target_id", "target_kind",
]
