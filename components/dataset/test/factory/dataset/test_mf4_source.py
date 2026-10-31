"""Focused security and lifetime tests for descriptor-backed MF4 ingest."""

from __future__ import annotations

import io
import os
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import numpy as np
import pytest

asammdf = pytest.importorskip("asammdf", reason="MF4 tests require the can-test group")
MDF = asammdf.MDF
Signal = asammdf.Signal
asammdf_version = asammdf.__version__

from factory.dataset.runtime.adapters import can_ingest
from factory.dataset.runtime.adapters.can_ingest import _iter_mf4_frames
from factory.dataset.runtime import mf4_source
from factory.dataset.runtime.mf4_source import open_mf4_stream


@pytest.fixture
def real_readonly_mf4(tmp_path: Path) -> Path:
    assert asammdf_version == "8.8.22"
    path = tmp_path / "generated.mf4"
    writer = MDF(version="4.10")
    try:
        writer.append(Signal(
            samples=np.array([1], dtype=np.uint8),
            timestamps=np.array([0.0]),
            name="probe",
        ))
        writer.save(path, overwrite=True)
    finally:
        writer.close()
    path.chmod(0o444)
    return path


def test_real_readonly_mf4_is_ingested_without_mode_change(
    real_readonly_mf4: Path,
) -> None:
    before = stat.S_IMODE(real_readonly_mf4.stat().st_mode)
    assert list(_iter_mf4_frames(
        str(real_readonly_mf4), object(), vehicle_id="vehicle",
    )) == []
    assert before == stat.S_IMODE(real_readonly_mf4.stat().st_mode) == 0o444


def test_filelike_remains_open_until_early_generator_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "capture.mf4"
    path.write_bytes(b"descriptor-backed")
    events: list[object] = []
    instances = []

    class FakeMDF:
        def __init__(self, source, **kwargs):
            assert isinstance(source, io.BufferedReader)
            assert stat.S_ISREG(os.fstat(source.fileno()).st_mode)
            assert kwargs == {"read_only": True}
            self.source = source
            self.groups = [SimpleNamespace(channels=[
                SimpleNamespace(name="Timestamp"),
                SimpleNamespace(name="CAN_DataFrame"),
            ])]
            instances.append(self)
            events.append("constructed")

        def get(self, _name, *, group, index):
            assert group == 0
            samples = (
                np.array([1.0]) if index == 0
                else np.array([1], dtype=np.uint8)
            )
            return SimpleNamespace(samples=samples)

        def close(self):
            events.append(("mdf-close", self.source.closed))

    monkeypatch.setitem(sys.modules, "asammdf", SimpleNamespace(MDF=FakeMDF))
    monkeypatch.setattr(can_ingest, "build_record", lambda *args: {"ok": True})
    records = _iter_mf4_frames(str(path), object(), vehicle_id="vehicle")
    assert next(records) == {"ok": True}
    source = instances[0].source
    assert source.closed is False
    records.close()
    assert events == ["constructed", ("mdf-close", False)]
    assert source.closed is True


def test_mdf_constructor_error_closes_stream(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "capture.mf4"
    path.write_bytes(b"not-mf4")
    captured = []

    def denied(source, **_kwargs):
        captured.append(source)
        raise PermissionError("read denied")

    monkeypatch.setitem(sys.modules, "asammdf", SimpleNamespace(MDF=denied))
    with pytest.raises(ValueError, match=str(path)) as exc_info:
        list(_iter_mf4_frames(str(path), object(), vehicle_id="vehicle"))
    assert isinstance(exc_info.value.__cause__, PermissionError)
    assert captured[0].closed is True


def test_symlink_and_non_regular_sources_are_rejected(
    real_readonly_mf4: Path, tmp_path: Path,
) -> None:
    symlink = tmp_path / "capture-link.mf4"
    symlink.symlink_to(real_readonly_mf4)
    directory = tmp_path / "capture-dir.mf4"
    directory.mkdir()
    fifo = tmp_path / "capture-fifo.mf4"
    os.mkfifo(fifo)

    for source in (symlink, directory, fifo):
        with pytest.raises(ValueError, match="not a regular file"):
            list(_iter_mf4_frames(str(source), object(), vehicle_id="vehicle"))


def test_path_replacement_during_open_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "capture.mf4"
    path.write_bytes(b"original")
    original_open = mf4_source.open_file_no_follow

    def replacing_open(source: Path, flags: int) -> int:
        descriptor = original_open(source, flags)
        source.unlink()
        source.write_bytes(b"replacement")
        return descriptor

    monkeypatch.setattr(mf4_source, "open_file_no_follow", replacing_open)
    with pytest.raises(ValueError, match="changed while opening"):
        with open_mf4_stream(path):
            pytest.fail("replacement source was accepted")

@pytest.mark.parametrize("iteration_error", [False, True])
def test_mdf_closes_before_stream_on_completion_or_iteration_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, iteration_error: bool,
) -> None:
    path = tmp_path / "capture.mf4"
    path.write_bytes(b"descriptor-backed")
    captured = []
    events = []

    class BrokenGroups:
        def __iter__(self):
            raise RuntimeError("iteration failed")

    class FakeMDF:
        def __init__(self, source, **_kwargs):
            self.source = source
            self.groups = BrokenGroups() if iteration_error else []
            captured.append(source)

        def close(self):
            events.append(("mdf-close", self.source.closed))

    monkeypatch.setitem(sys.modules, "asammdf", SimpleNamespace(MDF=FakeMDF))
    records = _iter_mf4_frames(str(path), object(), vehicle_id="vehicle")
    if iteration_error:
        with pytest.raises(RuntimeError, match="iteration failed"):
            list(records)
    else:
        assert list(records) == []
    assert events == [("mdf-close", False)]
    assert captured[0].closed is True
