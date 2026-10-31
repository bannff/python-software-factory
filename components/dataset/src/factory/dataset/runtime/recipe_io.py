"""JSONL record I/O helpers for dataset recipes.

Extracted from ``recipe.py`` to keep that module under the 200-LOC
factory ceiling while preserving backward compatibility — ``recipe.py``
re-exports ``load_records`` and ``records_content`` so existing
imports (``from factory.dataset.runtime.recipe import ...``) keep
working unchanged.
"""
from __future__ import annotations

import hashlib
import json
from typing import TYPE_CHECKING, Any

from .validation import dispatch_validator

if TYPE_CHECKING:
    from .contracts import DatasetGenerationRequest


def load_records(request: DatasetGenerationRequest, record_schema: str = "conversation") -> list[Any]:
    """Read immutable JSONL inputs and validate canonical records.

    Iterates every ``input_artifact`` on the request, checks its
    ``digest`` against the file contents (so tampering is detected
    before any stage runs), and feeds the union of records to
    ``dispatch_validator`` for schema-level validation.
    """
    # Lazy import breaks the recipe <-> recipe_io circular dependency
    # while preserving the existing ``path_from_uri`` location in
    # ``recipe.py`` (used widely across the codebase).
    from .atomic_io import read_bytes_no_follow
    from .recipe import path_from_uri

    records: list[Any] = []
    for source in request.input_artifacts:
        if source.artifact_role == "scenario_pack":
            continue
        path = path_from_uri(source.uri)
        content = read_bytes_no_follow(path)
        if hashlib.sha256(content).hexdigest() != source.digest:
            raise ValueError(f"Digest mismatch for input artifact: {source.uri}")
        for line in content.splitlines():
            if line.strip():
                records.append(json.loads(line))
    return list(dispatch_validator(records, record_schema=record_schema))


def records_content(records: list[Any], record_schema: str = "conversation") -> bytes:
    """Serialize canonical records deterministically as JSONL.

    The ``conversation`` schema serializes Pydantic models via
    ``model_dump(mode="json")`` (handles datetime, etc.); other schemas
    serialize raw dicts / primitives with ``sort_keys=True`` so
    identical inputs always hash to the same bytes.
    """
    if record_schema == "can_artifact":
        if len(records) != 1 or not isinstance(records[0], dict):
            raise ValueError("CAN artifact recipes must emit exactly one object")
        return json.dumps(
            records[0], sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        ).encode()
    if record_schema != "conversation":
        return b"".join(
            (json.dumps(
                r.model_dump(mode="json") if hasattr(r, "model_dump") else r,
                sort_keys=True,
            ) + "\n").encode()
            for r in records
        )
    return b"".join(
        (json.dumps(r.model_dump(mode="json"), sort_keys=True) + "\n").encode()
        for r in records
    )
