"""Deterministic credential/PII redaction for durable inbox content.

The inbox must never persist unredacted values (see M7
``m7-product-integration-design.md`` "Durable notifications and deep links").
``redact`` is a pure, idempotent transform: it strips known credential and
basic PII shapes to a fixed ``[redacted]`` marker and bounds length. It is the
single guarantee point applied at model-construction time for ``title`` and
``body`` so no producer can bypass it.
"""
from __future__ import annotations

import re

MAX_TITLE_CHARS = 200
MAX_BODY_CHARS = 2_000
_MARK = "[redacted]"

# Credential shapes — mirror the Migration source boundary so the two brick
# boundaries agree on what a secret looks like.
_CREDENTIAL_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj_)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
    re.compile(
        r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*KEY-----",
        re.S,
    ),
    re.compile(r"(?i)\b(?:bearer|token|secret|password|passwd|api[_-]?key)\b\s*[:=]\s*\S+"),
)

# Basic PII shapes.
_PII_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),        # email
    re.compile(r"\b(?:\d[ -]?){13,16}\b"),                                    # card-ish
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),                                     # US SSN
    re.compile(r"(?<!\d)\+?\d[\d ()-]{8,}\d(?!\d)"),                          # phone
)

_ALL_PATTERNS = _CREDENTIAL_PATTERNS + _PII_PATTERNS


def redact(text: str, *, limit: int) -> str:
    """Strip credential/PII shapes and bound length. Pure and idempotent."""
    scrubbed = text
    for pattern in _ALL_PATTERNS:
        scrubbed = pattern.sub(_MARK, scrubbed)
    scrubbed = " ".join(scrubbed.split())
    if len(scrubbed) > limit:
        scrubbed = scrubbed[: limit - 1] + "\u2026"
    return scrubbed


__all__ = ["MAX_BODY_CHARS", "MAX_TITLE_CHARS", "redact"]
