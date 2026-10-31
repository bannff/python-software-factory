"""Disk-backed Crew store — authority-partitioned, atomically written.

Records live under ``<root>/<authority_hash>/`` where the directory key is
a fixed-width hash of the validated ``(tenant_id, owner_id)`` — raw owner
text never appears in a path. Each Crew is ``<crew_id>.json``; the default
pointer is ``_default.json`` (a Crew id can never begin with ``_``, so the
two namespaces cannot collide). Writes go through a same-directory temp
file, ``fsync``, then ``os.replace`` for crash-atomic durability; the CAS
fencing itself lives in ``_CrewStoreBase`` under the owner lock.
"""
from __future__ import annotations

import errno
import json
import logging
import os
from pathlib import Path

from ..crew_contracts import CrewConfig
from .crew_store_base import _CrewStoreBase, authority_hash

logger = logging.getLogger(__name__)

_DEFAULT_FILE = "_default.json"


class DiskCrewStore(_CrewStoreBase):
    """Local-dev Crew backend mirroring the persona disk-store pattern."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root)

    def _owner_dir(self, tenant_id: str, owner_id: str) -> Path:
        return self._root / authority_hash(tenant_id, owner_id)

    def _load(self, tenant_id: str, owner_id: str) -> dict[str, CrewConfig]:
        directory = self._owner_dir(tenant_id, owner_id)
        if not directory.exists():
            return {}
        crews: dict[str, CrewConfig] = {}
        for path in sorted(directory.glob("*.json")):
            if path.name == _DEFAULT_FILE:
                continue
            try:
                config = CrewConfig.model_validate_json(path.read_text())
            except Exception as exc:  # noqa: BLE001 — skip bad file, keep rest
                logger.warning(
                    "Failed to load crew record=%s error_type=%s",
                    path.name, type(exc).__name__,
                )
                continue
            if config.tenant_id == tenant_id and config.owner_id == owner_id:
                crews[config.id] = config
        return crews

    def _store(self, config: CrewConfig) -> None:
        directory = self._owner_dir(config.tenant_id, config.owner_id)
        directory.mkdir(parents=True, exist_ok=True)
        _atomic_write(directory / f"{config.id}.json", config.model_dump_json())

    def _remove(self, tenant_id: str, owner_id: str, crew_id: str) -> None:
        path = self._owner_dir(tenant_id, owner_id) / f"{crew_id}.json"
        if path.exists():
            path.unlink()

    def _load_default(self, tenant_id: str, owner_id: str) -> str | None:
        path = self._owner_dir(tenant_id, owner_id) / _DEFAULT_FILE
        if not path.exists():
            return None
        try:
            value = json.loads(path.read_text()).get("crew_id")
        except Exception as exc:  # noqa: BLE001 — treat corruption as unset
            logger.warning(
                "Failed to load crew default error_type=%s", type(exc).__name__,
            )
            return None
        return value if isinstance(value, str) else None

    def _store_default(
        self, tenant_id: str, owner_id: str, crew_id: str | None,
    ) -> None:
        directory = self._owner_dir(tenant_id, owner_id)
        path = directory / _DEFAULT_FILE
        if crew_id is None:
            if path.exists():
                path.unlink()
            return
        directory.mkdir(parents=True, exist_ok=True)
        _atomic_write(path, json.dumps({"crew_id": crew_id}))


def _atomic_write(path: Path, payload: str) -> None:
    """Durable same-directory temp write + fsync + ``os.replace``."""
    tmp = path.with_name(f".{path.name}.tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, payload.encode())
        os.fsync(fd)
    finally:
        os.close(fd)
    os.replace(tmp, path)
    _sync_directory(path.parent)


def _sync_directory(directory: Path) -> None:
    """Sync a replaced directory entry when the host filesystem supports it."""
    dir_fd = os.open(directory, os.O_RDONLY)
    try:
        try:
            os.fsync(dir_fd)
        except OSError as exc:
            unsupported = {
                errno.EINVAL, errno.ENOTSUP,
                getattr(errno, "EOPNOTSUPP", errno.ENOTSUP),
            }
            if exc.errno not in unsupported:
                raise
    finally:
        os.close(dir_fd)


__all__ = ["DiskCrewStore"]
