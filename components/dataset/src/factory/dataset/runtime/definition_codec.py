"""Canonical JSON, digest, and bounded parsing for definition artifacts."""
from __future__ import annotations

import hashlib
import json

from .definition_models import DefinitionArtifact

DEFAULT_DEFINITION_MAX_BYTES = 1024 * 1024


def require_max_size(max_size_bytes: int) -> int:
    if type(max_size_bytes) is not int or max_size_bytes <= 0:
        raise ValueError("definition max size must be a positive integer")
    return max_size_bytes


def canonical_definition_bytes(artifact: DefinitionArtifact) -> bytes:
    return json.dumps(
        artifact.model_dump(mode="json"), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False, allow_nan=False,
    ).encode("utf-8")


def definition_digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def parse_definition_bytes(
    content: bytes, max_size_bytes: int,
) -> DefinitionArtifact:
    limit = require_max_size(max_size_bytes)
    if len(content) > limit:
        raise ValueError("definition artifact exceeds configured max size")
    artifact = DefinitionArtifact.model_validate_json(content)
    if canonical_definition_bytes(artifact) != content:
        raise ValueError("definition artifact bytes are not canonical JSON")
    return artifact


def parse_definition_json(
    content: str, max_size_bytes: int,
) -> DefinitionArtifact:
    limit = require_max_size(max_size_bytes)
    raw = content.encode("utf-8")
    if len(raw) > limit:
        raise ValueError("definition artifact exceeds configured max size before parse")
    return DefinitionArtifact.model_validate_json(raw)


__all__ = [
    "DEFAULT_DEFINITION_MAX_BYTES", "canonical_definition_bytes",
    "definition_digest", "parse_definition_bytes", "parse_definition_json",
    "require_max_size",
]
