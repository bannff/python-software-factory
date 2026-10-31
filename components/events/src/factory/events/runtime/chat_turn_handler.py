"""Chat-turn reward handler — scores the MAIN chat turn (bd:pfvo9 slice 2).

Subscribes to ``chat.turn.completed`` (emitted by the agent's
``WorkCompletedEmitterPlugin``). Routes the turn through the learning
reward-source seam (``learning_compute_reward`` → llm-judge source) and, if
a source produced a signal, emits the canonical ``reward.computed`` so the
existing memory / blockchain / improvement fan-out runs unchanged.

The agent's persona id is mapped to ``domain_class`` so the memory handler
tags the stored learning ``{agent_id}-learnings`` — exactly what
``LearningRecallPlugin`` queries next turn, closing the chat loop.
Reuses ``rewards_handler._emit_reward_event`` (DRY); no reward math here.
"""
from __future__ import annotations

import logging
from typing import Any

from .models import Event
from .rewards_handler import _emit_reward_event
from .learning_result import normalize_learning_result

logger = logging.getLogger(__name__)
_MAX_FEEDBACK_TEXT = 65_536

__all__ = ["handle_chat_turn_reward", "handle_chat_feedback"]


def handle_chat_turn_reward(event: Event, invoker: Any) -> dict[str, Any]:
    """Score a completed chat turn and emit reward.computed (if any signal)."""
    payload = event.payload
    run_id = payload.get("run_id", "")
    agent_id = payload.get("agent_id", "") or ""
    output = str(payload.get("output_summary") or "")[:_MAX_FEEDBACK_TEXT]
    if not run_id or not output:
        return {"skipped": True, "reason": "no run_id/output"}

    try:
        result = normalize_learning_result(invoker(
            "learning_compute_reward",
            run_id=run_id,
            domain_class=agent_id,
            workflow_type="chat",
            input_summary=str(payload.get("input_summary") or "")[:_MAX_FEEDBACK_TEXT],
            output_summary=output,
        ))
    except Exception as exc:
        logger.warning("chat-turn reward: compute failed (%s)", type(exc).__name__)
        return {"skipped": True, "error": "reward_computation_failed"}

    if result is None:
        return {"skipped": True, "error": "reward_computation_failed"}
    if not result.get("source_id"):
        # Every source abstained (e.g. trivial turn) — no reward spam.
        return {"skipped": True, "reason": "no reward signal"}

    # Canonical top-level fields are authoritative; raw is evidence only.
    if agent_id:
        payload["domain_class"] = agent_id
    reward = _emit_reward_event(invoker, event, result)
    logger.info(
        "chat-turn reward: run=%s agent=%s source=%s reward=%.1f",
        run_id, agent_id, result.get("source_id"),
        reward.get("reward_value", 0),
    )
    return {"run_id": run_id, "agent_id": agent_id, "reward": reward}


def handle_chat_feedback(event: Event, invoker: Any) -> dict[str, Any]:
    """Score an explicit user thumbs verdict (bd:pfvo9 S2).

    The FE emits ``chat.feedback`` {verdict, agent_id, thread_id, message_id}.
    We route it through the learning seam with NO output_summary so the
    llm-judge + gt-findings sources abstain and the user-feedback source is
    the sole signal (up → reward + mint, down → PENALIZED learning, zero
    tokens). The agent id rides as ``domain_class`` so the stored learning is
    tagged ``{agent_id}-learnings`` — recalled next turn by that persona.
    """
    payload = event.payload
    verdict = str(payload.get("verdict") or "").strip().lower()
    if verdict not in ("up", "down"):
        return {"skipped": True, "reason": "no thumbs verdict"}
    agent_id = payload.get("agent_id", "") or "companion-x-default"
    run_id = payload.get("run_id") or f"feedback-{payload.get('message_id', '')}"
    try:
        result = normalize_learning_result(invoker(
            "learning_compute_reward",
            run_id=run_id,
            domain_class=agent_id,
            workflow_type="feedback",
            feedback_verdict=verdict,
        ))
    except Exception as exc:
        logger.warning("chat-feedback reward: compute failed (%s)", type(exc).__name__)
        return {"skipped": True, "error": "reward_computation_failed"}
    if result is None:
        return {"skipped": True, "error": "reward_computation_failed"}
    if not result.get("source_id"):
        return {"skipped": True, "reason": "no reward signal"}
    # Keep canonical reward fields intact; raw is evidence for downstream memory.
    feedback_text = str(payload.get("content") or "")[:_MAX_FEEDBACK_TEXT]
    raw = {
        **result,
        "provenance": {
            **(result.get("provenance", {}) or {}),
            "feedback_text": feedback_text,
        },
    }
    # Carry context for the emitter + memory tag.
    payload["run_id"] = run_id
    payload["domain_class"] = agent_id
    reward = _emit_reward_event(invoker, event, raw)
    return {"run_id": run_id, "agent_id": agent_id,
            "verdict": verdict, "reward": reward}
