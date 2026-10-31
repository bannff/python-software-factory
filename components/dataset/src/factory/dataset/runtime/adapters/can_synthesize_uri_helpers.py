"""URI loading helpers for ``can_synthesize`` (Phase 5).

Keeps :mod:`can_synthesize` under the 200-LOC factory ceiling by
extracting the small but non-trivial file-loading concerns: a JSON
correlation matrix reader and a tiny path-resolver that normalizes
``file://`` URIs to local paths.

The JSON correlation matrix format is intentionally permissive — the
caller may pass any of the shapes accepted by
:func:`normalize_correlation_matrix` (list of triples, 2D array, or
dict with a ``matrix`` key). The raw parsed value is returned
verbatim and the downstream normalizer handles shape coercion.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlparse


def resolve_file_uri(uri: str) -> Path:
    """Convert a ``file://`` URI (or local path) to a resolved ``Path``.

    Raises ``ValueError`` for non-file schemes and defends against
    path traversal. Mirrors the security checks in
    :func:`factory.dataset.runtime.helpers.load_records_from_uri`.
    """
    if uri.startswith("file://"):
        parsed = urlparse(uri)
        if parsed.scheme != "file":
            raise ValueError(f"Only file:// URIs are supported: {uri}")
        raw_path = unquote(parsed.path)
    else:
        raw_path = uri
    if ".." in Path(raw_path).parts:
        raise ValueError(f"Path traversal not allowed: {uri}")
    return Path(raw_path).resolve()


def load_correlation_matrix_from_uri(uri: str) -> Any:
    """Load a precomputed correlation matrix from a ``file://`` URI.

    Returns the raw parsed JSON (any of the shapes accepted by
    :func:`normalize_correlation_matrix`). Raises ``ValueError`` on
    unsupported schemes or path traversal attempts.
    """
    return json.loads(resolve_file_uri(uri).read_text())


__all__ = [
    "load_correlation_matrix_from_uri",
    "resolve_file_uri",
]
