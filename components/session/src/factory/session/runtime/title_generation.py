"""Auto-generate a short session title from an excerpt (row 17, feature-map).

Manual rename (``session_rename``) already exists; this closes the other
half — automatic title generation. The FE supplies a short excerpt (first
user message + first assistant reply, typically) so this module stays free
of chat-transcript knowledge; it resolves a completion via the session's own
configured model (``title_complete.py``) and applies the result through the
EXISTING revision-fenced ``SessionLifecycle.rename`` — no new write path,
no new safety surface.
"""
from __future__ import annotations

import re

from .models import SessionRecord
from .title_complete import build_session_title_complete

_PROMPT = (
    "Summarize this conversation excerpt as a short chat title. "
    "Reply with ONLY the title text, no quotes, no punctuation at the end, "
    "5 words or fewer.\n\nExcerpt:\n{excerpt}"
)
_MAX_TITLE_LENGTH = 80


class TitleGenerationError(Exception):
    """The completion call itself failed (no model configured, network,
    provider error) — distinct from a session-not-found/revision-conflict,
    which the caller's own rename() call already raises."""


def _sanitize(raw: str) -> str:
    """Strip wrapping quotes/whitespace and hard-cap length — a model can
    return anything, this never trusts it blindly before it becomes a
    session title."""
    text = raw.strip().strip('"').strip("'").strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > _MAX_TITLE_LENGTH:
        text = text[:_MAX_TITLE_LENGTH].rstrip()
    return text or "Untitled chat"


def generate_title(model_id: str, excerpt: str) -> str:
    """Return a sanitized short title for ``excerpt``, or raise
    ``TitleGenerationError`` if the completion call itself fails."""
    try:
        complete = build_session_title_complete(model_id)
        raw = complete(_PROMPT.format(excerpt=excerpt[:4000]))
    except Exception as exc:
        raise TitleGenerationError(str(exc)) from exc
    return _sanitize(raw)


__all__ = ["TitleGenerationError", "generate_title"]
