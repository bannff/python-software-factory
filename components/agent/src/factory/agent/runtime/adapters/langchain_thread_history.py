"""Thread-lifecycle delegations from ``LangChainAgentRuntime`` to
``AsyncSqliteCheckpoints`` (history read, row 14 fork, row 16 regenerate
resume-point lookup).

Extracted from ``langchain_runtime.py`` (LOC ceiling) — these three
methods share the exact same shape (build the ``f"{agent_id}-{thread_id}"``
checkpoint key, delegate, return) and have no state of their own beyond
the ``AsyncSqliteCheckpoints`` instance they're given.
"""
from __future__ import annotations

from typing import Any

from .langchain_checkpoints import AsyncSqliteCheckpoints


async def history(checkpoints: AsyncSqliteCheckpoints, agent_id: str, thread_id: str) -> list[dict[str, Any]]:
    from .langchain_history import messages_to_agui
    return messages_to_agui(await checkpoints.history(f"{agent_id}-{thread_id}"))


async def fork_thread(
    checkpoints: AsyncSqliteCheckpoints, agent_id: str,
    source_thread_id: str, target_thread_id: str,
) -> bool:
    """Row 14 (feature-map) — copy a thread's full checkpoint history onto
    a new thread id, under the SAME persona/agent_id (a fork never changes
    which persona owns the conversation). Returns False when the source
    thread has no checkpoint yet."""
    return await checkpoints.copy_thread(
        f"{agent_id}-{source_thread_id}", f"{agent_id}-{target_thread_id}",
    )


async def checkpoint_before_message(
    checkpoints: AsyncSqliteCheckpoints, agent_id: str, thread_id: str, message_id: str,
) -> str | None:
    """Row 16 (feature-map) — the checkpoint id to resume from in order to
    regenerate the reply to a specific human message. See
    ``AsyncSqliteCheckpoints.checkpoint_before_message`` for the real
    chain-walk this delegates to. ``None`` when the message id never
    appears in this thread's checkpoint chain."""
    return await checkpoints.checkpoint_before_message(f"{agent_id}-{thread_id}", message_id)


async def regenerate_turn(
    runtime: Any, request_factory: Any,
    agent_id: str, thread_id: str, message_id: str, new_prompt: str,
) -> str | None:
    """Row 16 (feature-map) — re-run the reply to ``message_id`` with
    ``new_prompt``, creating a genuine sibling branch (the ORIGINAL reply
    stays independently resumable, never overwritten). Returns the new
    checkpoint id to persist as the thread's "current" branch (via
    ``session_set_active_checkpoint``), or ``None`` if ``message_id`` was
    never found in this thread's checkpoint chain."""
    resume_point = await runtime.checkpoint_before_message(agent_id, thread_id, message_id)
    if resume_point is None:
        return None
    from dataclasses import replace
    request = replace(request_factory(thread_id, new_prompt, agent_id), checkpoint_id=resume_point)
    result = await runtime.invoke(request)
    return result.metadata.get("checkpoint_id") or None


async def rewind_to_message(runtime: Any, agent_id: str, thread_id: str, message_id: str) -> str | None:
    """Row 15 (feature-map) — drop the transcript back to right after
    ``message_id`` landed, generating NOTHING new (unlike regenerate,
    which re-invokes onto a resume point). Reuses the EXACT same
    checkpoint-chain lookup regenerate uses — the checkpoint whose own
    message list ends in ``message_id`` IS the rewind target itself, not
    merely a resume point for a fresh call. Returns that checkpoint id to
    persist as the thread's "current" branch (via
    ``session_set_active_checkpoint``), or ``None`` if ``message_id`` was
    never found in this thread's checkpoint chain."""
    return await runtime.checkpoint_before_message(agent_id, thread_id, message_id)


def resulting_checkpoint_id(snapshot: Any) -> str:
    """Row 16 — pull the checkpoint id a graph invocation just wrote from
    the ``StateSnapshot`` returned by ``graph.aget_state(config)`` right
    after it (verified empirically to be the NEW id, not the input one)."""
    return str(snapshot.config["configurable"].get("checkpoint_id", ""))


async def capture_branch_id(graph: Any, thread_id: str) -> str:
    """Row 16 — the checkpoint a regenerate call just wrote. MUST read
    with a BARE thread config (no ``checkpoint_id``): ``aget_state`` on a
    config that still names the resume point returns THAT checkpoint
    unchanged, not the new one just written — a naive reused-config
    version silently returned the resume point itself on every
    regenerate, caught by a real test before shipping."""
    snapshot = await graph.aget_state({"configurable": {"thread_id": thread_id}})
    return resulting_checkpoint_id(snapshot)


__all__ = [
    "capture_branch_id", "checkpoint_before_message", "fork_thread",
    "history", "regenerate_turn", "resulting_checkpoint_id", "rewind_to_message",
]
