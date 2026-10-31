"""Frozen execution-authority checks for durable named workflows."""
from __future__ import annotations

from typing import Any

from .canonical import canonical_json
from .envelope import Envelope

_AUTHORITY_FIELDS = ("tenant_id", "principal_id", "session_id", "agent_id")


class AuthorityMismatchError(ValueError):
    """The current action is not authorized as the initiating principal."""


def authority_projection(envelope: Envelope) -> dict[str, Any]:
    """Project only execution authority, retaining explicit null identities.

    ``attributes`` is compared for authority-bearing context, but the
    invoker-injected per-call idempotency correlation (``workflow_attempt_id``)
    is excluded: ``NativeEnvelopeInvoker`` stamps it with each call's own
    ``idempotency_key``, so it legitimately differs between the enroll call
    (``run_key``) and any later action on the same run — e.g. the background
    drive's ``resume_run`` (``background-drive:<run_id>``). It is a correlation
    artifact, not execution authority, and must not gate the authority check.
    """
    attributes = {
        key: value for key, value in (envelope.attributes or {}).items()
        if key != "workflow_attempt_id"
    }
    return {
        **{name: getattr(envelope, name) for name in _AUTHORITY_FIELDS},
        "attributes": attributes,
    }


def execution_envelope(run: Any, action: Envelope) -> Envelope:
    """Return frozen initiation context for named runs after authority validation."""
    if not run.workflow_version_id:
        return action
    initiation = run.initiation_envelope
    if canonical_json(authority_projection(initiation)) != canonical_json(
        authority_projection(action)
    ):
        raise AuthorityMismatchError("workflow execution authority mismatch")
    return initiation
