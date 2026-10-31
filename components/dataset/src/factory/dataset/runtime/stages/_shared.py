"""Shared helpers for the native agentic-generation stages.

Ported from bannff/Agentic-Datasets@26cb683 (``stages/utils.py`` plus the
per-stage JSON parsers). Pure logic — no LLM client imports; stages receive
completions through the ``CompletionPort`` protocol.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def normalize_text(s: str) -> str:
    """Normalize text for deduplication."""
    return " ".join(s.lower().strip().split())


def hash_text(s: str) -> str:
    """Hash normalized text for deduplication."""
    return hashlib.sha256(normalize_text(s).encode("utf-8")).hexdigest()[:16]


def jaccard_diversity(a: str, b: str) -> float:
    """Calculate Jaccard diversity between two texts (0..1)."""
    at = set(normalize_text(a).split())
    bt = set(normalize_text(b).split())
    if not at and not bt:
        return 0.0
    inter = len(at & bt)
    union = len(at | bt) or 1
    return 1.0 - (inter / union)


def _try_loads(text: str) -> Any | None:
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


def _from_code_blocks(text: str) -> Any | None:
    """Extract JSON from ```json or plain ``` fenced blocks."""
    for marker in ("```json", "```"):
        if marker in text:
            start = text.find(marker) + len(marker)
            end = text.find("```", start)
            if end > start:
                parsed = _try_loads(text[start:end].strip())
                if parsed is not None:
                    return parsed
    return None


def parse_json_array(text: str) -> list[Any] | None:
    """Parse a JSON array from an LLM response that may contain markdown."""
    text = text.strip()
    parsed = _try_loads(text)
    if isinstance(parsed, list):
        return parsed
    parsed = _from_code_blocks(text)
    if isinstance(parsed, list):
        return parsed
    start, end = text.find("["), text.rfind("]")
    if start >= 0 and end > start:
        parsed = _try_loads(text[start : end + 1])
        if isinstance(parsed, list):
            return parsed
    return None


def parse_json_object(text: str, required_key: str | None = None) -> dict[str, Any] | None:
    """Parse a JSON object from an LLM response that may contain markdown."""

    def _accept(value: Any) -> dict[str, Any] | None:
        if isinstance(value, dict) and (required_key is None or required_key in value):
            return value
        return None

    text = text.strip()
    result = _accept(_try_loads(text))
    if result is not None:
        return result
    result = _accept(_from_code_blocks(text))
    if result is not None:
        return result
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        result = _accept(_try_loads(text[start : end + 1]))
        if result is not None:
            return result
    return None


def model_of(completion: Any) -> str | None:
    """Best-effort model identifier for stage metadata provenance."""
    return getattr(completion, "model_id", None)


def require_completion(completion: Any, stage_name: str) -> Any:
    """Fail loudly when use_llm=True but no completion port was bound."""
    if completion is None:
        raise ValueError(
            f"{stage_name} stage requires a bound completion port when use_llm=True; "
            "configure 'backend' (and optional 'model') in the recipe stage config"
        )
    return completion


class StageDefaults:
    """Default configuration values for stages.

    Centralizes magic numbers and default settings.
    """

    # Temperature settings by task type
    TEMPERATURE_CREATIVE = 0.8  # High diversity (agentinstruct variants)
    TEMPERATURE_BALANCED = 0.7  # Moderate (multi-turn expansion)
    TEMPERATURE_FOCUSED = 0.5  # Lower variance (tool injection)
    TEMPERATURE_PRECISE = 0.3  # Minimal variance (review/validation)

    # Token limits
    MAX_TOKENS_SHORT = 256  # Brief responses
    MAX_TOKENS_MEDIUM = 512  # Standard responses
    MAX_TOKENS_LONG = 1024  # Detailed responses
    MAX_TOKENS_MULTI = 2048  # Multi-turn conversations

    # Processing thresholds
    MIN_CONTENT_LENGTH = 10  # Minimum chars for meaningful content
    MAX_TOOL_CALLS_PER_MSG = 2  # Maximum tool calls to inject per message
    DIVERSITY_THRESHOLD = 0.3  # Minimum Jaccard diversity for dedup
