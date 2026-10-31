"""Credential-shape rejection for persisted client correlation IDs."""
from __future__ import annotations

import re

_CREDENTIALS = (
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"(?:gh[pousr]|github_pat)_[A-Za-z0-9_]{20,}"),
    re.compile(r"sk-(?:proj_)?[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?:sk|pk)_(?:live|test)_[A-Za-z0-9_]{16,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
)


def credential_clean_send_id(value: str) -> bool:
    """Return false for known credential shapes accepted by the ID alphabet."""
    return not any(pattern.fullmatch(value) for pattern in _CREDENTIALS)


__all__ = ["credential_clean_send_id"]
