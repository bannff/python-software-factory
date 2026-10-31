"""Safe failure normalization for typed MCP tool invocations."""

from __future__ import annotations

import logging
import sys
from typing import Any, Callable

from pydantic import ValidationError

from .tool_result import ToolResult

logger = logging.getLogger(__name__)
TOOL_EXECUTION_FAILED = "tool_execution_failed"
IDEMPOTENCY_KEY_CONFLICT = "idempotency_key_conflict"

# Item 12(a) (owner smoke #2, 2026-09-15 16:48): three status-bar widgets
# failed silently every 10s against real .storage because a validation
# failure logged only its TYPE, not its message — three separate bugs all
# needed the owner to notice by hand. ValueError/TypeError/ValidationError
# messages are schema-shaped (field names, constraint descriptions) by
# construction — Pydantic and our own field/model validators never embed
# caller secrets in them, unlike an arbitrary third-party exception's
# message, which might. Safe to log verbatim, same trust class as
# SafeDiagnostic below.
_SAFE_TO_LOG_MESSAGE = (ValueError, TypeError, ValidationError)


class SafeDiagnostic(ValueError):
    """An expected, pre-vetted domain-negative condition (e.g. an unknown
    adapter backend name) whose message is safe to log verbatim.

    Unlike an arbitrary exception — which ``tool_execution_failure`` logs by
    type identity only, per the ``protected_projection.safe_exception``
    precedent, to avoid capturing secrets/tokens that might be embedded in an
    unrelated error's text — a ``SafeDiagnostic`` is raised deliberately by
    trusted runtime code (e.g. ``GraphRuntime._create_graph``) with a message
    built entirely from caller-supplied config-shaped strings (backend
    names), never from arbitrary exception chains. Raise this instead of a
    bare ``ValueError`` when you want the specific diagnostic preserved in
    the server log instead of collapsed into the generic
    ``tool_execution_failed`` sentinel at the MCP boundary.
    """


def tool_execution_failure(func: Callable[..., Any]) -> ToolResult[None]:
    """Emit a secret-safe failure event and return the public typed envelope."""
    tool_identity = f"{func.__module__}.{func.__qualname__}"
    exc = sys.exc_info()[1]
    if isinstance(exc, SafeDiagnostic):
        logger.error(
            "typed_mcp_tool_execution_failed tool=%s diagnostic=%s",
            tool_identity, exc,
        )
    elif isinstance(exc, _SAFE_TO_LOG_MESSAGE):
        logger.error(
            "typed_mcp_tool_execution_failed tool=%s error_type=%s message=%s",
            tool_identity, type(exc).__name__, exc,
        )
    else:
        logger.error(
            "typed_mcp_tool_execution_failed tool=%s error_type=%s",
            tool_identity, type(exc).__name__ if exc is not None else "unknown",
        )
    return ToolResult(ok=False, data=None, error=TOOL_EXECUTION_FAILED)


def tool_idempotency_conflict(func: Callable[..., Any]) -> ToolResult[None]:
    """Return a stable failure when a key is reused for different input."""
    tool_identity = f"{func.__module__}.{func.__qualname__}"
    logger.error("typed_mcp_idempotency_key_conflict tool=%s", tool_identity)
    return ToolResult(ok=False, data=None, error=IDEMPOTENCY_KEY_CONFLICT)
