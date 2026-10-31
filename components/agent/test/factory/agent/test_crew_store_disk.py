"""Cross-platform durability tests for the local Crew disk adapter."""
from __future__ import annotations

import errno
import os
import stat
from pathlib import Path

import pytest

from factory.agent.runtime.adapters.crew_store_disk import DiskCrewStore
from factory.agent.runtime.crew_contracts import CrewConfig


def _crew() -> CrewConfig:
    return CrewConfig(
        tenant_id="tenant", owner_id="owner", id="crew", name="Crew",
        persona_id="companion-x-default", project="/tmp/project",
        memory_scope="scope", revision=1,
    )


def _directory_fsync_error(monkeypatch: pytest.MonkeyPatch, error: int) -> None:
    real_fsync = os.fsync

    def fsync(fd: int) -> None:
        if stat.S_ISDIR(os.fstat(fd).st_mode):
            raise OSError(error, os.strerror(error))
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", fsync)


def test_unsupported_directory_fsync_does_not_report_false_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _directory_fsync_error(monkeypatch, errno.EINVAL)
    store = DiskCrewStore(tmp_path / "crews")
    created = store.create_crew(_crew())
    assert created.revision == 1
    assert store.get_crew("tenant", "owner", "crew") == created


def test_unexpected_directory_fsync_error_remains_fail_closed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _directory_fsync_error(monkeypatch, errno.EIO)
    with pytest.raises(OSError, match="Input/output error"):
        DiskCrewStore(tmp_path / "crews").create_crew(_crew())
