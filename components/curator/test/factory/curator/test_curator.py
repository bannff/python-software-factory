"""Tests for curator brick — ROM ingest + compat scanning."""

from pathlib import Path

from factory.curator.interface import (
    CompatStatus,
    RomCandidate,
    assess_playability,
    check_compatibility,
    scan_rom_directory,
)


def test_scan_finds_rom_files(tmp_path: Path):
    # Arrange
    (tmp_path / "kinst.zip").write_bytes(b"\x00" * 100)
    (tmp_path / "subdir").mkdir()
    (tmp_path / "subdir" / "kigold.z64").write_bytes(b"\x00" * 200)
    (tmp_path / "game.chd").write_bytes(b"\x00" * 50)

    # Act
    results = scan_rom_directory(tmp_path)

    # Assert
    filenames = {r.filename for r in results}
    assert filenames == {"kinst.zip", "kigold.z64", "game.chd"}
    assert all(isinstance(r, RomCandidate) for r in results)


def test_scan_ignores_non_rom_files(tmp_path: Path):
    # Arrange
    (tmp_path / "readme.txt").write_text("hello")
    (tmp_path / "notes.md").write_text("# notes")
    (tmp_path / "save.srm").write_bytes(b"\x00")

    # Act
    results = scan_rom_directory(tmp_path)

    # Assert
    assert results == []


def test_compat_ok_when_core_and_bios_present(tmp_path: Path):
    # Arrange
    cores = tmp_path / "cores"
    cores.mkdir()
    (cores / "snes9x_libretro.so").write_bytes(b"")
    bios = tmp_path / "bios"
    bios.mkdir()
    candidate = RomCandidate(
        path=tmp_path / "game.sfc", filename="game.sfc", extension=".sfc", size_bytes=1024
    )

    # Act
    report = check_compatibility(candidate, cores, bios)

    # Assert
    assert report.status == CompatStatus.OK
    assert report.system == "snes"
    assert report.core_hint == "snes9x"


def test_compat_missing_bios(tmp_path: Path):
    # Arrange
    cores = tmp_path / "cores"
    cores.mkdir()
    (cores / "mgba_libretro.so").write_bytes(b"")
    bios = tmp_path / "bios"
    bios.mkdir()
    # gba_bios.bin NOT created
    candidate = RomCandidate(
        path=tmp_path / "game.gba", filename="game.gba", extension=".gba", size_bytes=2048
    )

    # Act
    report = check_compatibility(candidate, cores, bios)

    # Assert
    assert report.status == CompatStatus.MISSING_BIOS
    assert report.system == "gba"


def test_compat_missing_core(tmp_path: Path):
    # Arrange
    cores = tmp_path / "cores"
    cores.mkdir()
    # No mupen64plus_next core
    bios = tmp_path / "bios"
    bios.mkdir()
    candidate = RomCandidate(
        path=tmp_path / "game.z64", filename="game.z64", extension=".z64", size_bytes=4096
    )

    # Act
    report = check_compatibility(candidate, cores, bios)

    # Assert
    assert report.status == CompatStatus.MISSING_CORE
    assert report.system == "n64"
    assert report.core_hint == "mupen64plus_next"


def test_assess_playability_is_passthrough(tmp_path: Path):
    # Arrange
    candidate = RomCandidate(
        path=tmp_path / "game.nes", filename="game.nes", extension=".nes", size_bytes=512
    )
    from factory.curator.compat import CompatReport

    report = CompatReport(candidate=candidate, status=CompatStatus.OK, system="nes", core_hint="mesen")

    # Act
    result = assess_playability(report)

    # Assert
    assert result is report
