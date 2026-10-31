"""Revision-safe global steering documents injected into Agent prompts."""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import os
from pathlib import Path

from ..authoring.roots import ensure_root, resolve_root

_MAX_BYTES = 262_144


@dataclass(frozen=True)
class SteeringDocument:
    id: str
    title: str
    content: str
    sha256: str


def steering_root() -> Path:
    """The user-owned durable steering root (never the installed package)."""
    return resolve_root("steering").path


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


def _read(path: Path, root: Path) -> SteeringDocument | None:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > _MAX_BYTES:
        return None
    try:
        path.resolve(strict=True).relative_to(root)
        raw = path.read_bytes()
        text = raw.decode("utf-8")
    except (OSError, UnicodeError, ValueError):
        return None
    title = next((line.lstrip("# ").strip() for line in text.splitlines()
                  if line.strip()), path.stem)
    return SteeringDocument(path.stem, title[:200] or path.stem, text, _digest(raw))


def list_steering() -> list[SteeringDocument]:
    root_path = steering_root()
    if not root_path.exists() or root_path.is_symlink():
        return []
    root = root_path.resolve()
    return [doc for path in sorted(root.glob("*.md")) if (doc := _read(path, root))]


def read_steering(document_id: str) -> SteeringDocument | None:
    root_path = steering_root()
    if not root_path.exists() or root_path.is_symlink():
        return None
    root = root_path.resolve()
    return _read(root / f"{document_id}.md", root)


def _replace(document_id: str, content: str, expected_sha256: str | None) -> SteeringDocument:
    root = ensure_root("steering", refuse_symlink=True).path.resolve(strict=True)
    target = root / f"{document_id}.md"
    current = _read(target, root)
    if expected_sha256 is None and target.exists():
        raise FileExistsError(document_id)
    if expected_sha256 is not None and (current is None or current.sha256 != expected_sha256):
        raise RuntimeError("steering_revision_conflict")
    encoded = content.strip().encode("utf-8") + b"\n"
    if len(encoded) > _MAX_BYTES:
        raise ValueError("steering_too_large")
    temporary = root / f".{document_id}.{os.getpid()}.tmp"
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(temporary, flags, 0o600)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        raise
    result = _read(target, root)
    if result is None:
        raise OSError("steering_write_failed")
    return result


def create_steering(document_id: str, content: str) -> SteeringDocument:
    return _replace(document_id, content, None)


def update_steering(document_id: str, content: str, expected_sha256: str) -> SteeringDocument:
    return _replace(document_id, content, expected_sha256)


def delete_steering(document_id: str, expected_sha256: str) -> None:
    root = ensure_root("steering", refuse_symlink=True).path.resolve(strict=True)
    target = root / f"{document_id}.md"
    current = _read(target, root)
    if current is None:
        raise FileNotFoundError(document_id)
    if current.sha256 != expected_sha256:
        raise RuntimeError("steering_revision_conflict")
    target.unlink()


def steering_prompt() -> tuple[str, str]:
    documents = list_steering()
    if not documents:
        return "", _digest(b"")
    body = "\n\n".join(f"## {doc.title}\n{doc.content.strip()}" for doc in documents)
    return f"# Workspace steering\n{body}", _digest(body.encode("utf-8"))


def apply_steering(base_prompt: str) -> tuple[str, str]:
    text, digest = steering_prompt()
    return (f"{base_prompt}\n\n{text}" if text else base_prompt), digest


__all__ = [
    "SteeringDocument", "apply_steering", "create_steering", "delete_steering",
    "list_steering", "read_steering", "steering_prompt", "steering_root", "update_steering",
]
