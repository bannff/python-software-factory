"""Shared validation and canonicalization for model passports."""
from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any
from urllib.parse import urlparse

_DIGEST_RE = re.compile(r"^[0-9a-f]{64}$")
_MEDIA_TYPE_RE = re.compile(r"^[A-Za-z0-9!#$&^_.+-]+/[A-Za-z0-9!#$&^_.+-]+$")
_FORMAT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+-]{0,63}$")


def require_text(value: str, label: str) -> str:
    if not value or value != value.strip():
        raise ValueError(f"{label} must be non-empty and trimmed")
    return value


def require_digest(value: str, label: str) -> str:
    if not _DIGEST_RE.fullmatch(value):
        raise ValueError(f"{label} must be lowercase SHA-256")
    return value


def require_uri(value: str, label: str) -> str:
    require_text(value, label)
    parsed = urlparse(value)
    if not parsed.scheme or (parsed.scheme == "file" and not parsed.path.startswith("/")):
        raise ValueError(f"{label} must be an absolute URI")
    if parsed.scheme != "file" and not (parsed.netloc or parsed.path):
        raise ValueError(f"{label} must be an absolute URI")
    return value


def require_media_type(value: str) -> str:
    if not _MEDIA_TYPE_RE.fullmatch(value):
        raise ValueError("media_type must be a valid type/subtype")
    return value.lower()


def require_format(value: str) -> str:
    if not _FORMAT_RE.fullmatch(value):
        raise ValueError("format must be a stable format token")
    return value.lower()


def require_finite_json(value: Any, label: str = "config") -> Any:
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{label} must not contain NaN or Infinity")
        return value
    if isinstance(value, (list, tuple)):
        for item in value:
            require_finite_json(item, label)
        return value
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"{label} keys must be non-empty strings")
            require_finite_json(item, label)
        return value
    raise ValueError(f"{label} must contain only JSON values")


def canonical_json(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        allow_nan=False,
    ).encode()


def semantic_digest(value: Any) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


__all__ = [
    "canonical_json", "require_digest", "require_finite_json", "require_format",
    "require_media_type", "require_text", "require_uri", "semantic_digest",
]
