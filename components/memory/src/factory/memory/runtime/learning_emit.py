"""Closure-observability emit helper for memory.retrieve.

Produces the `learning.applied` canonical learning event whenever a retrieve
call returns at least one memory tagged with a `*-learnings` suffix (the
workflow_rl signature). Exists as a sibling to ``emit.py`` so that
``runtime.py`` stays SRP-focused on retrieval orchestration.

Contract: bd python-factory-o7t8. Architect-locked payload shape lives in
``factory.events.runtime.learning_contracts.LearningAppliedPayload``. This
module emits a plain dict matching that shape — emission is best-effort and
must not raise back into the retrieve caller (mirrors emit.py L33-34).
"""
from __future__ import annotations

import logging
from hashlib import sha256
from typing import TYPE_CHECKING

from factory.memory.runtime.emit import emit_memory_event

if TYPE_CHECKING:
    from factory.memory.runtime.models import Memory

logger = logging.getLogger(__name__)

_LEARNINGS_TAG_SUFFIX = "-learnings"
_QUERY_TRUNC = 256
_HASH_LEN = 16


def _has_learnings_tag(memory: "Memory") -> bool:
    """True iff any tag in metadata.tags ends with the `-learnings` suffix."""
    tags = memory.metadata.get("tags") if memory.metadata else None
    if not isinstance(tags, (list, tuple, set)):
        return False
    return any(
        isinstance(tag, str) and tag.endswith(_LEARNINGS_TAG_SUFFIX)
        for tag in tags
    )


def _first_run_id(memories: list["Memory"]) -> str:
    """Return the first non-empty metadata.run_id across the result set."""
    for memory in memories:
        run_id = memory.metadata.get("run_id") if memory.metadata else None
        if isinstance(run_id, str) and run_id:
            return run_id
    return ""


def _agent_id_for(memories: list["Memory"], user_id: str) -> str:
    """Resolve agent_id from metadata if present, else fall back to user_id."""
    for memory in memories:
        agent_id = memory.metadata.get("agent_id") if memory.metadata else None
        if isinstance(agent_id, str) and agent_id:
            return agent_id
    return user_id or ""


def emit_learning_applied(
    memories: list["Memory"],
    query: str,
    user_id: str,
) -> None:
    """Emit a `learning.applied` event when retrieved memories include learnings.

    No-op when no memory carries a ``*-learnings`` tag. Swallows all
    exceptions so retrieval flow is never disturbed.
    """
    try:
        if not memories or not any(_has_learnings_tag(m) for m in memories):
            return

        truncated_query = (query or "")[:_QUERY_TRUNC]
        query_hash = sha256(truncated_query.encode()).hexdigest()[:_HASH_LEN]
        run_id = _first_run_id(memories)
        agent_id = _agent_id_for(memories, user_id)
        idempotency_key = f"learning_applied:{run_id}:{agent_id}:{query_hash}"

        payload = {
            "run_id": run_id,
            "workflow_run_id": run_id,
            "agent_id": agent_id,
            "retrieved_count": len(memories),
            "retrieved_memory_ids": [m.id for m in memories],
            "query": truncated_query,
            "idempotency_key": idempotency_key,
        }
        emit_memory_event(
            event_type="learning.applied",
            payload=payload,
            user_id=user_id,
        )
    except Exception as e:  # pragma: no cover - defensive guard
        logger.debug("learning.applied emission skipped: %s", e)
