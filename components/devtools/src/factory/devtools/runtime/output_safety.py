"""Terminal output sanitation before activity or model handoff."""
from __future__ import annotations

import re

_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_SENSITIVE = tuple(re.compile(value, re.IGNORECASE) for value in (
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"\bAKIA[0-9A-Z]{16}\b",
    r"\bsk-[A-Za-z0-9_-]{16,}\b",
    r"\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*\S+",
))


class OutputRefused(RuntimeError):
    pass


def sanitize_output(value: str) -> str:
    clean = _ANSI.sub("", value)
    clean = "".join(
        char for char in clean
        if char in "\n\t" or 32 <= ord(char) <= 126 or ord(char) >= 160
    )
    if any(pattern.search(clean) for pattern in _SENSITIVE):
        raise OutputRefused("command output contained credential-like content")
    return clean


__all__ = ["OutputRefused", "sanitize_output"]
