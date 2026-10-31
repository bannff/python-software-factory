"""S2M stage: single-turn to multi-turn conversion using LLM reasoning.

Ported from bannff/Agentic-Datasets@26cb683 (``stages/s2m_v2.py``). Pure
logic — completions arrive through the ``CompletionPort`` protocol.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator

from ..ports import CompletionPort
from ..records import ConversationRecord, Message
from ._prompts_s2m import S2M_SYSTEM, S2M_TRANSFORM
from ._shared import StageDefaults, model_of, parse_json_array, require_completion

logger = logging.getLogger(__name__)


def _generate_multiturn(
    question: str, answer: str, completion: CompletionPort
) -> list[Message] | None:
    """Generate a multi-turn conversation using the LLM."""
    prompt = S2M_TRANSFORM.format(question=question, answer=answer)
    try:
        response = completion.get_completion(
            prompt,
            system_prompt=S2M_SYSTEM,
            temperature=StageDefaults.TEMPERATURE_BALANCED,
            max_tokens=StageDefaults.MAX_TOKENS_MULTI,
        )
        messages_data = parse_json_array(response)
        if not messages_data:
            logger.warning("Failed to parse S2M response as JSON")
            return None

        messages: list[Message] = []
        for m in messages_data:
            role = str(m.get("role", "")).strip()
            content = str(m.get("content", "")).strip()
            if role in ("user", "assistant", "system") and content:
                messages.append(Message(role=role, content=content))

        # Ensure we have at least 4 messages (2 turns)
        if len(messages) >= 4:
            return messages
        logger.warning("S2M generated only %s messages, need at least 4", len(messages))
        return None
    except Exception as error:
        logger.warning("S2M LLM generation failed: %s", error)
        return None


def _fallback_multiturn(rec: ConversationRecord) -> ConversationRecord:
    """Deterministic multi-turn fallback without an LLM."""
    return ConversationRecord(
        messages=[
            rec.messages[0],
            rec.messages[1],
            Message(role="user", content="Can you provide an example?"),
            Message(
                role="assistant",
                content="[Example would be provided here with LLM generation enabled]",
            ),
        ],
        metadata={
            **(rec.metadata or {}),
            "stage": "s2m",
            "original_turns": 2,
            "generated_turns": 4,
            "via": "fallback",
        },
        source=rec.source,
        id=rec.id,
    )


def s2m(
    records: Iterable[ConversationRecord],
    *,
    min_turns: int = 4,
    max_turns: int = 10,
    use_llm: bool = True,
    completion: CompletionPort | None = None,
) -> Iterator[ConversationRecord]:
    """Convert single-turn Q&A pairs to multi-turn conversations."""
    if use_llm:
        completion = require_completion(completion, "s2m")
    logger.info("S2M: use_llm=%s, min_turns=%s", use_llm, min_turns)

    for rec in records:
        # If already multi-turn, pass through
        if len(rec.messages) > 2:
            logger.debug("Record %s already multi-turn (%s messages)", rec.id, len(rec.messages))
            yield rec
            continue

        # Check for single-turn Q&A structure
        if (
            len(rec.messages) == 2
            and rec.messages[0].role == "user"
            and rec.messages[1].role == "assistant"
        ):
            if use_llm:
                messages = _generate_multiturn(
                    rec.messages[0].content, rec.messages[1].content, completion
                )
                if messages:
                    if len(messages) > max_turns:
                        messages = messages[:max_turns]
                    yield ConversationRecord(
                        messages=messages,
                        metadata={
                            **(rec.metadata or {}),
                            "stage": "s2m",
                            "original_turns": 2,
                            "generated_turns": len(messages),
                            "via": "llm",
                            "model": model_of(completion),
                        },
                        source=rec.source,
                        id=rec.id,
                    )
                    continue
            yield _fallback_multiturn(rec)
        elif len(rec.messages) == 1 and rec.messages[0].role == "user":
            # Single user message - add placeholder assistant response
            yield ConversationRecord(
                messages=[
                    rec.messages[0],
                    Message(
                        role="assistant",
                        content="[Response would be generated with LLM enabled]",
                    ),
                ],
                metadata={**(rec.metadata or {}), "stage": "s2m", "via": "fallback"},
                source=rec.source,
                id=rec.id,
            )
        else:
            # Unknown structure, pass through
            yield rec
