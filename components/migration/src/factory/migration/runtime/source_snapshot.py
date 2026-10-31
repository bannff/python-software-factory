"""Trusted temp snapshot of an operator-configured KiroCrew home.

The operator root is passed in by the runtime — this module contains NO env
or public-path logic. It stages ONLY the enumerated allowlist below; no
unknown, secret, session, model, log, or upload file is ever opened. Every
path component is ``lstat``-checked for symlinks, leaves are opened
``O_NOFOLLOW`` through parent directory descriptors (openat), and the open
descriptor is ``fstat``-checked for regular-file/single-link/owner/size and
re-checked after read to detect mutation. ``memory.db`` uses the SQLite online
backup API (committed WAL rows included) plus ``integrity_check`` — never a
plain copy with ``immutable=1``.
"""
from __future__ import annotations

import hashlib
import os
import stat
from datetime import datetime, timezone
from pathlib import Path

from .source_models import (
    MAX_DB_BYTES, MAX_FILE_BYTES, MAX_FILES, ReasonCode, SnapshotManifest,
    StagedFile, sha256_hex,
)
from .source_sqlite import DatabaseSnapshotError, backup_database

DB_REL = "memory.db"
LESSONS_REL = "lessons.jsonl"
CRON_RELS: tuple[str, ...] = ("crons.json", "cron/jobs.json")
PREFERENCES_REL = "workspace/memory/preferences.md"
PROJECTS_REL = "workspace/memory/projects.md"
HISTORY_DIR = "workspace/memory/history"

_OPEN_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_CLOEXEC", 0)
_DIR_FLAGS = _OPEN_FLAGS | getattr(os, "O_DIRECTORY", 0)
_READ_CHUNK = 1024 * 1024


class SnapshotError(Exception):
    """A single allowlisted path failed a safety gate (kind is skipped)."""

    def __init__(self, reason: ReasonCode, rel_path: str) -> None:
        super().__init__(f"{reason.value}: {rel_path}")
        self.reason = reason
        self.rel_path = rel_path


def _descend(root: Path, comps: list[str], rel: str) -> tuple[int, list[int]]:
    """Open directory descriptors for ``comps`` under ``root`` (openat chain)."""
    cur = os.open(str(root), _DIR_FLAGS)
    opened = [cur]
    try:
        for comp in comps:
            meta = os.lstat(comp, dir_fd=cur)
            if stat.S_ISLNK(meta.st_mode):
                raise SnapshotError(ReasonCode.SYMLINK, rel)
            if not stat.S_ISDIR(meta.st_mode):
                raise SnapshotError(ReasonCode.NOT_REGULAR, rel)
            cur = os.open(comp, _DIR_FLAGS, dir_fd=cur)
            opened.append(cur)
        return cur, opened
    except Exception:
        for descriptor in opened:
            os.close(descriptor)
        raise


def _gate_stat(st: os.stat_result, rel: str, expected_uid: int) -> None:
    if not stat.S_ISREG(st.st_mode):
        raise SnapshotError(ReasonCode.NOT_REGULAR, rel)
    if st.st_nlink != 1:
        raise SnapshotError(ReasonCode.HARDLINK, rel)
    if st.st_uid != expected_uid:
        raise SnapshotError(ReasonCode.OWNER_MISMATCH, rel)
    cap = MAX_DB_BYTES if rel == DB_REL else MAX_FILE_BYTES
    if st.st_size > cap:
        raise SnapshotError(ReasonCode.SIZE_EXCEEDED, rel)


def _open_leaf_fd(root: Path, rel: str, expected_uid: int) -> tuple[int, os.stat_result]:
    parts = rel.split("/")
    cur, opened = _descend(root, parts[:-1], rel)
    try:
        leaf = parts[-1]
        if stat.S_ISLNK(os.lstat(leaf, dir_fd=cur).st_mode):
            raise SnapshotError(ReasonCode.SYMLINK, rel)
        try:
            fd = os.open(leaf, _OPEN_FLAGS, dir_fd=cur)
        except OSError as exc:
            code = ReasonCode.SYMLINK if exc.errno == getattr(os, "ELOOP", 62) else ReasonCode.UNREADABLE
            raise SnapshotError(code, rel) from exc
    finally:
        for d in opened:
            os.close(d)
    st = os.fstat(fd)
    try:
        _gate_stat(st, rel, expected_uid)
    except SnapshotError:
        os.close(fd)
        raise
    return fd, st


def _unchanged(a: os.stat_result, b: os.stat_result) -> bool:
    return (a.st_ino, a.st_dev, a.st_size, a.st_mtime_ns) == (
        b.st_ino, b.st_dev, b.st_size, b.st_mtime_ns)


def _stage_regular(root: Path, rel: str, dest_dir: Path, expected_uid: int) -> StagedFile:
    fd, before = _open_leaf_fd(root, rel, expected_uid)
    cap = MAX_DB_BYTES if rel == DB_REL else MAX_FILE_BYTES
    try:
        digest = hashlib.sha256()
        out_path = dest_dir / rel
        out_path.parent.mkdir(parents=True, exist_ok=True)
        size = 0
        with open(fd, "rb", closefd=False) as src, open(out_path, "wb") as dst:
            while chunk := src.read(_READ_CHUNK):
                size += len(chunk)
                if size > cap:
                    raise SnapshotError(ReasonCode.SIZE_EXCEEDED, rel)
                digest.update(chunk)
                dst.write(chunk)
        if not _unchanged(before, os.fstat(fd)):
            raise SnapshotError(ReasonCode.MUTATED, rel)
    finally:
        os.close(fd)
    return StagedFile(rel_path=rel, size=size, sha256=digest.hexdigest())


def _stage_db(root: Path, dest_dir: Path, expected_uid: int) -> StagedFile:
    """Online-backup ``memory.db`` (committed WAL included) + integrity check."""
    fd, before = _open_leaf_fd(root, DB_REL, expected_uid)
    out_path = dest_dir / DB_REL
    try:
        try:
            size = backup_database(root / DB_REL, out_path, fd, before)
        except DatabaseSnapshotError as exc:
            raise SnapshotError(exc.reason, DB_REL) from exc
    finally:
        os.close(fd)
    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    return StagedFile(rel_path=DB_REL, size=size, sha256=digest)


def _history_members(root: Path) -> list[str]:
    try:
        cur, opened = _descend(root, HISTORY_DIR.split("/"), HISTORY_DIR)
    except (SnapshotError, OSError):
        return []
    try:
        names = sorted(n for n in os.listdir(cur) if n.endswith(".md"))
    finally:
        for d in opened:
            os.close(d)
    return [f"{HISTORY_DIR}/{n}" for n in names]


def stage_snapshot(root: Path, dest_dir: Path) -> tuple[SnapshotManifest, list[SnapshotError]]:
    """Stage the allowlist into ``dest_dir``; return manifest + skip errors.

    A per-file safety failure is collected (the kind is later skipped) rather
    than aborting the whole snapshot. Unknown/secret files are never in the
    allowlist, so they are never touched.
    """
    root = Path(root)
    expected_uid = os.stat(str(root)).st_uid
    candidates = [DB_REL, LESSONS_REL, PREFERENCES_REL, PROJECTS_REL]
    candidates.extend(r for r in CRON_RELS if (root / r).exists())
    candidates.extend(_history_members(root))
    staged: list[StagedFile] = []
    errors: list[SnapshotError] = []
    for rel in candidates:
        if len(staged) >= MAX_FILES:
            errors.append(SnapshotError(ReasonCode.COUNT_EXCEEDED, rel))
            continue
        if not (root / rel).exists():
            continue
        try:
            staged.append(
                _stage_db(root, dest_dir, expected_uid) if rel == DB_REL
                else _stage_regular(root, rel, dest_dir, expected_uid))
        except SnapshotError as exc:
            errors.append(exc)
    ordered = tuple(sorted(staged, key=lambda f: f.rel_path))
    digest = sha256_hex("\n".join(f"{f.rel_path}:{f.sha256}" for f in ordered))
    manifest = SnapshotManifest(
        files=ordered, digest=digest, created_at=datetime.now(timezone.utc))
    return manifest, errors


__all__ = ["SnapshotError", "stage_snapshot", "DB_REL", "LESSONS_REL",
           "CRON_RELS", "PREFERENCES_REL", "PROJECTS_REL", "HISTORY_DIR"]
