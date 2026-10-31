"""Canonical artifact slug derivation."""
from __future__ import annotations

import re
import unicodedata

_NON_SLUG = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    normalized = unicodedata.normalize("NFKD", name)
    ascii_name = normalized.encode("ascii", "ignore").decode().lower()
    base = _NON_SLUG.sub("-", ascii_name).strip("-") or "artifact"
    return base[:80].rstrip("-") or "artifact"


def slug_candidate(base: str, attempt: int) -> str:
    if attempt == 1:
        return base
    suffix = f"-{attempt}"
    return f"{base[:80 - len(suffix)].rstrip('-')}{suffix}"


__all__ = ["slug_candidate", "slugify"]
