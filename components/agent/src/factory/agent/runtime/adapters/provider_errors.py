"""Map LLM-provider HTTP failures to actionable user-facing messages.

A blanket "Chat is temporarily unavailable" hides the one thing the user
can act on: a 402 from the provider means credits are exhausted, and no
amount of retrying fixes that. OpenRouter (via langchain-openai) raises
``openai.APIStatusError`` subclasses carrying ``.status_code``.
"""
from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

_GENERIC = "Chat is temporarily unavailable. Please retry."

_CREDIT = (
    "LLM provider credits exhausted — top up your account "
    "(openrouter.ai/credits) and try again."
)
_AUTH = (
    "LLM provider authentication failed — check the configured API key "
    "for the chat model."
)
_RATE = (
    "LLM provider rate limit reached — wait a moment and try again."
)


def provider_error_message(exc: Exception) -> str:
    """Return a user-facing message, specific when the status code is known."""
    status = getattr(exc, "status_code", None)
    if status == 402:
        return _CREDIT
    if status in (401, 403):
        return _AUTH
    if status == 429:
        return _RATE
    return _GENERIC


def log_stream_failure(exc: Exception) -> None:
    """Log the underlying provider failure (status first when present)."""
    status = getattr(exc, "status_code", None)
    if status is not None:
        logger.warning(
            "chat stream failed status_code=%s error_type=%s: %s",
            status, type(exc).__name__, exc,
        )
    else:
        logger.warning(
            "chat stream failed error_type=%s: %s", type(exc).__name__, exc,
        )


__all__ = ["provider_error_message", "log_stream_failure"]
