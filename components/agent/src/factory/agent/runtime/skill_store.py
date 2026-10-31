"""Layered on-disk skill store: user-authored root over packaged built-ins.

Reads resolve over BOTH roots (packaged built-ins win an id collision), so
a skill authored at runtime is visible to the model without giving up the
shipped catalogue. Writes only ever touch the user root, and a packaged id
stays non-collidable and non-deletable.

Path handling stays symlink/traversal-safe, and every filesystem effect of
an authoring action lives here rather than in the MCP surface.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from ..authoring.roots import (
    AuthoringRootUnavailable, ensure_root, packaged_skills_root, resolve_root,
)

logger = logging.getLogger(__name__)
MAX_SKILL_BYTES = 400_000


class BuiltinSkillError(ValueError):
    """Raised when a caller tries to mutate a packaged built-in skill."""


@dataclass(frozen=True)
class StoredSkill:
    id: str
    name: str
    description: str
    path: Path
    builtin: bool


def read_roots() -> tuple[tuple[Path, bool], ...]:
    """Ordered ``(root, builtin)`` pairs for reads; built-ins win."""
    packaged = packaged_skills_root()
    user = resolve_root("skills").path
    return ((packaged, True), (user, False))


def _frontmatter(path: Path) -> dict[str, Any]:
    try:
        text = path.read_text(encoding="utf-8")
        parts = text.split("---", 2)
        value = yaml.safe_load(parts[1]) if text.startswith("---") and len(parts) == 3 else {}
        return value if isinstance(value, dict) else {}
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        logger.debug("Cannot read skill %s: %s", path, error)
        return {}


def _in_root(root: Path, skill_id: str) -> Path | None:
    """Return the skill directory under ``root`` when it is safe to use."""
    directory = root / skill_id
    path = directory / "SKILL.md"
    if directory.is_symlink() or not directory.is_dir():
        return None
    if path.is_symlink() or not path.is_file():
        return None
    try:
        path.resolve(strict=True).relative_to(root.resolve())
    except (OSError, ValueError):
        return None
    return directory


def skill_dir(skill_id: str) -> Path | None:
    """Resolve one skill directory over the layered roots."""
    for root, _builtin in read_roots():
        if not root.exists() or root.is_symlink():
            continue
        directory = _in_root(root, skill_id)
        if directory is not None:
            return directory
    return None


def _stored(skill_id: str, path: Path, builtin: bool) -> StoredSkill:
    meta = _frontmatter(path)
    return StoredSkill(
        id=skill_id, name=str(meta.get("name") or skill_id),
        description=str(meta.get("description") or "").strip(), path=path, builtin=builtin,
    )


def list_skills() -> list[StoredSkill]:
    """Enumerate every skill visible to the model, built-ins first."""
    found: dict[str, StoredSkill] = {}
    for root, builtin in read_roots():
        if not root.exists() or root.is_symlink():
            continue
        for directory in sorted(root.iterdir()):
            path = directory / "SKILL.md"
            if (directory.is_dir() and not directory.is_symlink()
                    and path.is_file() and not path.is_symlink()):
                found.setdefault(directory.name, _stored(directory.name, path, builtin))
    return sorted(found.values(), key=lambda skill: skill.id)


def read_skill(skill_id: str) -> tuple[StoredSkill, str] | None:
    """Return one skill plus its body, or ``None`` when unusable/absent."""
    directory = skill_dir(skill_id)
    if directory is None:
        return None
    path = directory / "SKILL.md"
    if path.stat().st_size > MAX_SKILL_BYTES:
        return None
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
    parts = text.split("---", 2)
    body = parts[2].strip() if text.startswith("---") and len(parts) == 3 else text.strip()
    builtin = directory.parent == packaged_skills_root()
    return _stored(skill_id, path, builtin), body


def _write_root() -> Path:
    """The user skill root writes target, refusing a symlinked/packaged root."""
    root = ensure_root("skills", refuse_symlink=True)
    if root.path == packaged_skills_root():
        raise AuthoringRootUnavailable(
            root.variable, root.path, "points at the packaged built-in skills",
        )
    return root.path.resolve(strict=True)


def add_skill(skill_id: str, name: str, description: str, body: str) -> StoredSkill:
    """Write a NEW skill into the user root; never shadow a built-in id."""
    if skill_dir(skill_id) is not None:
        raise FileExistsError(skill_id)
    root = _write_root()
    directory = root / skill_id
    directory.mkdir(mode=0o700, exist_ok=False)
    temporary = directory / ".SKILL.md.tmp"
    target = directory / "SKILL.md"
    header = yaml.safe_dump(
        {"name": name.strip(), "description": description.strip()},
        sort_keys=False, allow_unicode=True,
    )
    encoded = f"---\n{header}---\n\n{body.strip()}\n".encode("utf-8")
    if len(encoded) > MAX_SKILL_BYTES:
        directory.rmdir()
        raise ValueError("skill_too_large")
    try:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(temporary, flags, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(encoded)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    except BaseException:
        temporary.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
        directory.rmdir()
        raise
    return StoredSkill(skill_id, name.strip(), description.strip(), target, False)


def delete_skill(skill_id: str) -> bool:
    """Remove a USER skill directory; packaged ids are not deletable."""
    if _in_root(packaged_skills_root(), skill_id) is not None:
        raise BuiltinSkillError(skill_id)
    root = _write_root()
    directory = _in_root(root, skill_id)
    if directory is None:
        return False
    for child in directory.iterdir():
        if child.is_symlink() or child.is_dir():
            return False
        child.unlink()
    directory.rmdir()
    return True


__all__ = [
    "BuiltinSkillError", "MAX_SKILL_BYTES", "StoredSkill", "add_skill", "delete_skill",
    "list_skills", "read_roots", "read_skill", "skill_dir",
]
