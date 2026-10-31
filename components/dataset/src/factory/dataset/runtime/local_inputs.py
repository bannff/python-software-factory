"""Canonical local input paths for Dataset MCP translation and workers."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import unquote, urlparse


def path_from_uri(uri: str) -> Path:
    """Resolve the strict local file URI shape supported by Dataset workers."""
    parsed = urlparse(uri)
    decoded = unquote(parsed.path)
    if (
        parsed.scheme != "file"
        or parsed.netloc not in {"", "localhost"}
        or parsed.query
        or parsed.fragment
        or not decoded.startswith("/")
    ):
        raise ValueError(f"Only local file URIs are supported: {uri}")
    if ".." in Path(decoded).parts:
        raise ValueError(f"Path traversal is not supported: {uri}")
    return Path(decoded).resolve()


def path_from_uri_no_follow(uri: str) -> Path:
    """Parse a local file URI without resolving links before a no-follow open."""
    parsed = urlparse(uri)
    decoded = unquote(parsed.path)
    path = Path(decoded)
    if (
        parsed.scheme != "file"
        or parsed.netloc not in {"", "localhost"}
        or parsed.query
        or parsed.fragment
        or not path.is_absolute()
    ):
        raise ValueError("Only absolute local file URIs are supported")
    if ".." in path.parts:
        raise ValueError("Path traversal is not supported")
    return path


def canonicalize_local_input(value: str) -> str:
    """Return a canonical file URI for an absolute path or local file URI."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Dataset local input must be a non-empty absolute path or file URI")
    raw = value.strip()
    candidate = Path(raw)
    if candidate.is_absolute() and urlparse(raw).scheme == "":
        if ".." in candidate.parts:
            raise ValueError(f"Path traversal is not supported: {value}")
        return candidate.resolve().as_uri()
    if not raw.startswith("file://"):
        raise ValueError(
            f"Dataset local input must be an absolute path or local file:// URI: {value}"
        )
    return path_from_uri(raw).as_uri()


__all__ = [
    "canonicalize_local_input", "path_from_uri", "path_from_uri_no_follow",
]
