"""Bounded stdout/stderr capture for command telemetry.

Language- and domain-agnostic: emits a bounded *tail* of raw output plus the
true length so callers can see truncation. It never parses or interprets the
output (no test/build metrics here) — interpretation is a caller concern so the
sandbox stays a faithful, agnostic executor.
"""
from __future__ import annotations

import os

_DEFAULT_TAIL_CHARS = 2000


def tail_limit() -> int:
    """Resolve the per-stream tail size from ``SANDBOX_OUTPUT_TAIL_CHARS``.

    ``0`` disables capture entirely; a malformed value falls back to the default.
    """
    raw = os.environ.get("SANDBOX_OUTPUT_TAIL_CHARS")
    if raw is None:
        return _DEFAULT_TAIL_CHARS
    try:
        return max(0, int(raw))
    except ValueError:
        return _DEFAULT_TAIL_CHARS


def _tail(text: str, limit: int) -> str:
    if limit <= 0 or not text:
        return ""
    return text if len(text) <= limit else text[-limit:]


def capture_output(stdout: str, stderr: str) -> dict[str, object]:
    """Return bounded tails plus full lengths and a truncation flag."""
    limit = tail_limit()
    return {
        "stdout_chars": len(stdout),
        "stderr_chars": len(stderr),
        "stdout_tail": _tail(stdout, limit),
        "stderr_tail": _tail(stderr, limit),
        "output_truncated": limit > 0 and (len(stdout) > limit or len(stderr) > limit),
    }
