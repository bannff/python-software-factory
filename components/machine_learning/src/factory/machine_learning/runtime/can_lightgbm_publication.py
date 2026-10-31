"""Filesystem publication primitives for lifecycle LightGBM effect trees."""
from __future__ import annotations

import errno
import os
from pathlib import Path
import stat

from .passport_tree_seal import remove_staging_tree


def effect_paths(root: Path, effect_id: str) -> tuple[Path, Path]:
    return root / effect_id, root / f".{effect_id}.staging"


def finalize(staging: Path, final: Path, parent: Path) -> None:
    try:
        os.rename(staging, final)
    except OSError as exc:
        if exc.errno not in {errno.EEXIST, errno.ENOTEMPTY} or not final.exists():
            raise
        remove_staging_tree(staging)
    fd = os.open(parent, os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def fsync_tree(root: Path) -> None:
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    paths = [root]
    for directory, dirs, files in os.walk(root, followlinks=False):
        paths.extend(Path(directory) / name for name in dirs + files)
    for path in reversed(paths):
        info = path.lstat()
        mode = flags | (getattr(os, "O_DIRECTORY", 0) if stat.S_ISDIR(info.st_mode) else 0)
        fd = os.open(path, mode)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)


__all__ = ["effect_paths", "finalize", "fsync_tree"]
