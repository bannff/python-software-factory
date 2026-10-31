"""Unit tests for source-snapshot safety gate helpers."""
from __future__ import annotations

import os
import stat as stat_mod

import pytest

from factory.migration.runtime import source_snapshot as snap
from factory.migration.runtime.source_models import ReasonCode
from factory.migration.runtime.source_snapshot import SnapshotError, _gate_stat, _unchanged


class _FakeStat:
    def __init__(self, mode, nlink, uid, size):
        self.st_mode = mode
        self.st_nlink = nlink
        self.st_uid = uid
        self.st_size = size


def test_gate_stat_owner_mismatch():
    st = _FakeStat(stat_mod.S_IFREG | 0o600, 1, 4242, 10)
    with pytest.raises(SnapshotError) as exc:
        _gate_stat(st, "memory.db", expected_uid=os.getuid())
    assert exc.value.reason == ReasonCode.OWNER_MISMATCH


def test_gate_stat_hardlink_rejected():
    st = _FakeStat(stat_mod.S_IFREG | 0o600, 2, os.getuid(), 10)
    with pytest.raises(SnapshotError) as exc:
        _gate_stat(st, "memory.db", expected_uid=os.getuid())
    assert exc.value.reason == ReasonCode.HARDLINK


def test_gate_stat_size_exceeded():
    st = _FakeStat(stat_mod.S_IFREG | 0o600, 1, os.getuid(), snap.MAX_FILE_BYTES + 1)
    with pytest.raises(SnapshotError) as exc:
        _gate_stat(st, "workspace/memory/preferences.md", expected_uid=os.getuid())
    assert exc.value.reason == ReasonCode.SIZE_EXCEEDED


def test_gate_stat_db_gets_larger_cap():
    st = _FakeStat(stat_mod.S_IFREG | 0o600, 1, os.getuid(), snap.MAX_FILE_BYTES + 1)
    _gate_stat(st, "memory.db", expected_uid=os.getuid())  # under 64 MiB DB cap: ok


def test_gate_stat_not_regular():
    st = _FakeStat(stat_mod.S_IFIFO | 0o600, 1, os.getuid(), 1)
    with pytest.raises(SnapshotError) as exc:
        _gate_stat(st, "memory.db", expected_uid=os.getuid())
    assert exc.value.reason == ReasonCode.NOT_REGULAR


class _S:
    def __init__(self, ino, dev, size, mt):
        self.st_ino, self.st_dev, self.st_size, self.st_mtime_ns = ino, dev, size, mt


def test_unchanged_true_when_identical():
    assert _unchanged(_S(1, 1, 10, 5), _S(1, 1, 10, 5))


def test_unchanged_detects_size_and_mtime_mutation():
    assert not _unchanged(_S(1, 1, 10, 5), _S(1, 1, 20, 5))
    assert not _unchanged(_S(1, 1, 10, 5), _S(1, 1, 10, 9))
    assert not _unchanged(_S(1, 1, 10, 5), _S(2, 1, 10, 5))
