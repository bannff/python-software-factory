"""ReviewInstruct stage: LLM-powered multi-agent review.

Ported from bannff/Agentic-Datasets@26cb683 (``stages/reviewinstruct_v2.py``).
A chairman evaluates conversations and a refiner improves the ones below the
accept threshold. Pure logic — completions arrive through ``CompletionPort``.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Iterator
from typing import Any

from ..ports import CompletionPort
from ..records import ConversationRecord, Message
from ._prompts_reviewinstruct import (
    CHAIRMAN_REVIEW,
    CHAIRMAN_SYSTEM,
    REFINER_IMPROVE,
    REFINER_SYSTEM,
)
from ._shared import (
    StageDefaults,
    model_of,
    parse_json_array,
    parse_json_object,
    require_completion,
)

logger = logging.getLogger(__name__)


def _format_conversation(messages: list[Message]) -> str:
    """Format messages for review, including tool interactions."""
    lines: list[str] = []
    for msg in messages:
        role = msg.role.upper()
        if msg.tool_calls:
            tools = ", ".join(tc.name for tc in msg.tool_calls)
            lines.append(f"{role}: {msg.content}\n  [Calls: {tools}]")
        elif msg.role == "tool":
            lines.append(f"TOOL ({msg.tool_name}): {msg.content}")
        else:
            lines.append(f"{role}: {msg.content}")
    return "\n\n".join(lines)


def _review_conversation(messages: list[Message], completion: CompletionPort) -> dict[str, Any]:
    """Get a quality review from the LLM chairman."""
    prompt = CHAIRMAN_REVIEW.format(conversation=_format_conversation(messages))
    try:
        response = completion.get_completion(
            prompt,
            system_prompt=CHAIRMAN_SYSTEM,
            temperature=StageDefaults.TEMPERATURE_PRECISE,  # Lower for consistent judgment
            max_tokens=StageDefaults.MAX_TOKENS_LONG,
        )
        review = parse_json_object(response, required_key="decision")
        if review:
            return review
        # Default to accept if parsing fails
        return {"decision": "accept", "overall_score": 3, "issues": ["Parse failed"]}
    except Exception as error:
        logger.warning("Review failed: %s", error)
        return {"decision": "accept", "overall_score": 3, "issues": [str(error)]}


def _refine_conversation(
    messages: list[Message], feedback: dict[str, Any], completion: CompletionPort
) -> list[Message] | None:
    """Refine a conversation based on review feedback."""
    prompt = REFINER_IMPROVE.format(
        conversation=_format_conversation(messages),
        feedback=json.dumps(feedback.get("issues", [])),
        guidance=feedback.get("refinement_guidance", "Improve clarity and completeness"),
    )
    try:
        response = completion.get_completion(
            prompt,
            system_prompt=REFINER_SYSTEM,
            temperature=0.6,
            max_tokens=StageDefaults.MAX_TOKENS_MULTI,
        )
        messages_data = parse_json_array(response)
        if not messages_data:
            return None
        result: list[Message] = []
        for m in messages_data:
            role = str(m.get("role", "")).strip()
            content = str(m.get("content", "")).strip()
            if role in ("user", "assistant", "system", "tool") and content:
                result.append(Message(role=role, content=content))
        return result if len(result) >= 2 else None
    except Exception as error:
        logger.warning("Refinement failed: %s", error)
        return None


def _with_meta(rec: ConversationRecord, messages: list[Message], **extra: Any) -> ConversationRecord:
    meta: dict[str, Any] = dict(rec.metadata or {})
    meta.update({"stage": "reviewinstruct", **extra})
    return ConversationRecord(messages=messages, metadata=meta, source=rec.source, id=rec.id)


def reviewinstruct(
    records: Iterable[ConversationRecord],
    *,
    accept_threshold: float = 3.5,
    max_iterations: int = 2,
    use_llm: bool = True,
    completion: CompletionPort | None = None,
) -> Iterator[ConversationRecord]:
    """Review and optionally refine conversations using LLM agents."""
    if use_llm:
        completion = require_completion(completion, "reviewinstruct")
    logger.info("ReviewInstruct: threshold=%s, max_iter=%s", accept_threshold, max_iterations)

    for rec in records:
        if not use_llm:
            yield _with_meta(rec, rec.messages, reviewed=False, via="disabled")
            continue
        try:
            current_messages = rec.messages
            review: dict[str, Any] | None = None
            iteration = 0

            while iteration < max_iterations:
                review = _review_conversation(current_messages, completion)
                score = review.get("overall_score", 3)
                decision = review.get("decision", "accept")
                if decision == "accept" or score >= accept_threshold:
                    break
                refined = _refine_conversation(current_messages, review, completion)
                if refined:
                    current_messages = refined
                    iteration += 1
                else:
                    # Refinement failed, accept as-is
                    break

            yield _with_meta(
                rec,
                current_messages,
                reviewed=True,
                via="llm",
                model=model_of(completion),
                decision=review.get("decision", "accept") if review else "accept",
                score=review.get("overall_score", 3) if review else 3,
                iterations=iteration,
            )
        except Exception as error:
            logger.warning("ReviewInstruct failed for %s: %s", rec.id, error)
            yield _with_meta(rec, rec.messages, reviewed=False, via="error")
