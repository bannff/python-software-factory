"""Defense-in-depth secret-shape guard for export bundle content.

Structural exclusion (owner_secrets has no read tool) is the PRIMARY
guarantee — this module is the secondary check: every string that will
enter the bundle is scanned, and any credential-shaped substring found is
scrubbed. A record that STILL trips a pattern after scrubbing is rejected
outright (not shipped redacted) — a tripped record after scrubbing means
the pattern matched something the scrub didn't fully remove, which is a
bug worth surfacing, not content worth shipping.

Deliberately narrower than migration's own ``redact()`` (used for bounded,
truncated PREVIEW samples): no blanket "any 32+ char alnum/hex run" rule,
which would corrupt ordinary long memory/lesson content that happens to be
a long word or hash-looking token. This guard only removes shapes that are
credential-specific.
"""
from __future__ import annotations

import re

_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?i)-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*KEY-----", re.S),
    re.compile(r"(?i)\b(?:bearer|authorization)\s*[: ]\s*\S+"),
    re.compile(r"(?i)\b(?:api[_-]?key|secret|password|passwd)\b\s*[:=]\s*\S+"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
)

_MARK = "[redacted]"


def scrub(text: str) -> str:
    """Remove credential-shaped substrings, preserving everything else."""
    scrubbed = text
    for pattern in _PATTERNS:
        scrubbed = pattern.sub(_MARK, scrubbed)
    return scrubbed


def still_trips(text: str) -> bool:
    """True if a credential shape survives — the record must be rejected,
    not shipped, when this is true after ``scrub`` already ran once."""
    return any(pattern.search(text) for pattern in _PATTERNS)


__all__ = ["scrub", "still_trips"]
