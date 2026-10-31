"""Generate a rolling conversation summary from a transcript excerpt
(row 18, feature-map).

Mirrors ``title_generation.py`` exactly: the caller (FE) supplies a short
transcript excerpt so this module stays free of chat-transcript knowledge;
it resolves a completion over the session's OWN configured model (the same
credential-free ``ChatProfile`` chat itself resolves to, via
``title_complete.py``) and returns a sanitized summary. Applying it to the
session is the caller's job, through the existing revision-fenced
``SessionLifecycle.set_summary`` — no new write path, no new safety surface.
"""
from __future__ import annotations

import re

from .title_complete import build_session_title_complete

_PROMPT = (
    "You are maintaining a rolling summary of a conversation. Read the "
    "transcript excerpt below and write a concise summary of what has "
    "happened so far — the key topics, decisions made, and any open "
    "questions. Use a few short sentences or bullet points. Reply with "
    "ONLY the summary text, no preamble.\n\nTranscript:\n{excerpt}"
)
_MAX_SUMMARY_LENGTH = 8_000


class SummaryGenerationError(Exception):
    """The completion call itself failed (no model configured, network,
    provider error) — distinct from a session-not-found/revision-conflict,
    which the caller's own ``set_summary`` call already raises."""


def _sanitize(raw: str) -> str:
    """Trim and hard-cap length — a model can return anything, and this is
    about to be persisted as durable session state, so it is never trusted
    blindly."""
    text = raw.strip()
    if len(text) > _MAX_SUMMARY_LENGTH:
        text = text[:_MAX_SUMMARY_LENGTH].rstrip()
    return text


def generate_summary(model_id: str, excerpt: str) -> str:
    """Return a sanitized rolling summary for ``excerpt``, or raise
    ``SummaryGenerationError`` if the completion call itself fails. The
    excerpt is truncated before sending so an enormous transcript can't
    blow the model's context window."""
    try:
        complete = build_session_title_complete(model_id)
        raw = complete(_PROMPT.format(excerpt=excerpt[:24_000]))
    except Exception as exc:
        raise SummaryGenerationError(str(exc)) from exc
    return _sanitize(raw)


__all__ = ["SummaryGenerationError", "generate_summary"]
