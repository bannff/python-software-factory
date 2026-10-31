"""AgentInstruct stage: LLM-powered instruction transformation.

Ported from bannff/Agentic-Datasets@26cb683 (``stages/agentinstruct_v2.py``).
Implements the Microsoft AgentInstruct methodology: each seed instruction is
expanded into k diverse variants via LLM reasoning (or deterministic suffix
templates when ``use_llm=False``). Pure logic — completions arrive through
the ``CompletionPort`` protocol; no LLM client imports.
"""

from __future__ import annotations

import logging
from collections.abc import Iterable, Iterator
from typing import Any

from ..ports import CompletionPort
from ..records import ConversationRecord, Message
from ._prompts_agentinstruct import (
    AGENTINSTRUCT_SYSTEM,
    COMPLEXITY_PROMPTS,
    COMPLEXITY_SYSTEM,
    TRANSFORM_PROMPTS,
)
from ._shared import StageDefaults, hash_text, jaccard_diversity, model_of, require_completion

logger = logging.getLogger(__name__)

DEFAULT_TRANSFORMS = ["qa", "writing", "coding", "reasoning"]


def _transform_with_llm(
    seed: str, transform_type: str, completion: CompletionPort
) -> str | None:
    """Transform a seed instruction using LLM reasoning."""
    prompt_template = TRANSFORM_PROMPTS.get(transform_type)
    if not prompt_template:
        logger.warning("Unknown transform type: %s", transform_type)
        return None
    try:
        response = completion.get_completion(
            prompt_template.format(seed=seed),
            system_prompt=AGENTINSTRUCT_SYSTEM,
            temperature=StageDefaults.TEMPERATURE_CREATIVE,  # Higher for diversity
            max_tokens=StageDefaults.MAX_TOKENS_MEDIUM,
        )
        return response.strip()
    except Exception as error:
        logger.warning("LLM transform failed for %s: %s", transform_type, error)
        return None


def _adjust_complexity(
    instruction: str, level: str, completion: CompletionPort
) -> str | None:
    """Adjust instruction complexity using the LLM."""
    prompt_template = COMPLEXITY_PROMPTS.get(level)
    if not prompt_template:
        return None
    try:
        response = completion.get_completion(
            prompt_template.format(instruction=instruction),
            system_prompt=COMPLEXITY_SYSTEM,
            temperature=0.6,
            max_tokens=StageDefaults.MAX_TOKENS_MEDIUM,
        )
        return response.strip()
    except Exception as error:
        logger.warning("Complexity adjustment failed: %s", error)
        return None


def _fallback_transform(seed: str, transform_type: str) -> str:
    """Deterministic suffix-based transformation when the LLM is unavailable."""
    suffixes = {
        "qa": " Explain this in a Q&A format with clear answers.",
        "writing": " Provide a comprehensive explanation with examples.",
        "coding": " Include code examples and implementation details.",
        "classification": " Compare and categorize the different approaches.",
        "summarization": " Summarize the key points concisely.",
        "extraction": " Extract the essential facts and data points.",
        "reasoning": " Walk through the logic step by step.",
    }
    return seed.strip() + suffixes.get(transform_type, "")


def agentinstruct(
    records: Iterable[ConversationRecord],
    *,
    k_variants: int = 3,
    transforms: list[str] | None = None,
    complexity_levels: list[str] | None = None,
    dedupe: bool = True,
    use_llm: bool = True,
    completion: CompletionPort | None = None,
) -> Iterator[ConversationRecord]:
    """Expand each record into k diverse instruction variants (fan-out)."""
    if use_llm:
        completion = require_completion(completion, "agentinstruct")
    transform_types = transforms or DEFAULT_TRANSFORMS
    k = max(1, int(k_variants))
    logger.info("AgentInstruct: k=%s, transforms=%s, use_llm=%s", k, transform_types, use_llm)

    for rec in records:
        # Find first user message as seed
        user_idx = next((i for i, m in enumerate(rec.messages) if m.role == "user"), None)
        if user_idx is None:
            yield rec
            continue

        seed = rec.messages[user_idx].content
        origin_id = rec.id

        # Generate variants using selected transforms
        candidates: list[tuple[str, str]] = []  # (variant_text, transform_type)
        for transform_type in transform_types:
            if len(candidates) >= k:
                break
            if use_llm:
                variant = _transform_with_llm(seed, transform_type, completion)
                if variant and variant != seed:
                    candidates.append((variant, transform_type))
            else:
                candidates.append((_fallback_transform(seed, transform_type), transform_type))

        # Apply complexity adjustments if requested
        if complexity_levels and use_llm:
            adjusted: list[tuple[str, str]] = []
            for variant, ttype in candidates:
                for level in complexity_levels:
                    if len(adjusted) >= k:
                        break
                    adj = _adjust_complexity(variant, level, completion)
                    if adj:
                        adjusted.append((adj, f"{ttype}_{level}"))
            if adjusted:
                candidates = adjusted[:k]

        # Deduplicate by content hash
        if dedupe:
            unique: dict[str, tuple[str, str]] = {}
            for variant, ttype in candidates:
                unique.setdefault(hash_text(variant), (variant, ttype))
            candidates = list(unique.values())

        candidates = candidates[:k]

        for i, (variant, transform_type) in enumerate(candidates, start=1):
            # Rewrite first user message; keep rest unchanged
            new_messages = [
                Message(role="user", content=variant)
                if idx == user_idx and msg.role == "user"
                else msg
                for idx, msg in enumerate(rec.messages)
            ]
            meta: dict[str, Any] = dict(rec.metadata or {})
            meta.update({
                "stage": "agentinstruct",
                "origin_id": origin_id,
                "variant_id": f"v{i}",
                "transform_type": transform_type,
                "variant_prompt": variant,
                "diversity_score": jaccard_diversity(variant, seed),
                "llm_generated": use_llm,
                "model": model_of(completion) if use_llm else None,
            })
            yield ConversationRecord(
                messages=new_messages,
                id=(rec.id or "rec") + f"::v{i}",
                source=rec.source,
                metadata=meta,
            )
