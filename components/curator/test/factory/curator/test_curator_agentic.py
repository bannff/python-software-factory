"""B8 Agentic Verification — fixture-driven ROM pipeline scenario.

Builds a realistic ROM tree and drives the full scan->compat->assess pipeline,
judging each status as a domain expert. Probes edge cases: uppercase extensions,
empty dirs, nonexistent paths, recursive subdirs, orphan .cue, unknown extensions.
"""

from pathlib import Path

import pytest

from factory.curator.interface import (
    CompatStatus,
    assess_playability,
    check_compatibility,
    scan_rom_directory,
)


@pytest.fixture
def rom_tree(tmp_path: Path) -> dict[str, Path]:
    """Build a realistic multi-scenario fixture tree."""
    # --- cores dir (partial — some cores present, some missing) ---
    cores = tmp_path / "cores"
    cores.mkdir()
    (cores / "snes9x_libretro.so").write_bytes(b"\x00")
    (cores / "mgba_libretro.so").write_bytes(b"\x00")
    (cores / "pcsx_rearmed_libretro.so").write_bytes(b"\x00")
    (cores / "mame2003_plus_libretro.so").write_bytes(b"\x00")
    # mupen64plus_next NOT present — forces MISSING_CORE for n64

    # --- bios dir (partial — GBA bios missing) ---
    bios = tmp_path / "bios"
    bios.mkdir()
    (bios / "scph1001.bin").write_bytes(b"\x00" * 32)
    # gba_bios.bin NOT present — forces MISSING_BIOS for .gba

    # --- ROM tree ---
    roms = tmp_path / "roms"
    roms.mkdir()

    # Scenario 1: valid SNES ROM, core present, no BIOS needed -> OK
    (roms / "chrono_trigger.sfc").write_bytes(b"\x00" * 2048)

    # Scenario 2: valid arcade ZIP, core present, no BIOS -> OK
    (roms / "kinst.zip").write_bytes(b"\x00" * 4096)

    # Scenario 3: N64 ROM, core MISSING -> MISSING_CORE
    subdir = roms / "n64"
    subdir.mkdir()
    (subdir / "goldeneye.z64").write_bytes(b"\x00" * 8192)

    # Scenario 4: GBA ROM, core present but BIOS missing -> MISSING_BIOS
    (roms / "metroid_fusion.gba").write_bytes(b"\x00" * 4096)

    # Scenario 5: PSX .cue WITHOUT companion .bin or .chd -> MISSING_CHD
    (roms / "ff7.cue").write_bytes(b"FILE ff7.bin BINARY\n")

    # Scenario 6: PSX .bin standalone, core+BIOS present -> OK
    (roms / "crash.bin").write_bytes(b"\x00" * 1024)

    # Scenario 7: non-ROM files (must NOT appear in scan results)
    (roms / "readme.txt").write_text("hello")
    (roms / "notes.md").write_text("# notes")
    (roms / "gamelist.nfo").write_text("<game/>")

    # Scenario 8: uppercase extension -> SHOULD be ingested (.suffix.lower())
    (roms / "SONIC.ZIP").write_bytes(b"\x00" * 512)

    # Scenario 9: deeply nested subdir
    deep = roms / "psx" / "ntsc"
    deep.mkdir(parents=True)
    (deep / "mgs.iso").write_bytes(b"\x00" * 2048)

    # Scenario 10: unknown extension -> NOT ingested
    (roms / "mystery.xyz").write_bytes(b"\x00" * 100)

    return {"roms": roms, "cores": cores, "bios": bios}


class TestScanEdgeCases:
    def test_scan_finds_all_rom_extensions_recursively(self, rom_tree):
        results = scan_rom_directory(rom_tree["roms"])
        filenames = {r.filename for r in results}
        # All ROM files including nested and uppercase
        expected = {
            "chrono_trigger.sfc", "kinst.zip", "goldeneye.z64",
            "metroid_fusion.gba", "ff7.cue", "crash.bin",
            "SONIC.ZIP", "mgs.iso",
        }
        assert expected == filenames

    def test_scan_excludes_non_rom_extensions(self, rom_tree):
        results = scan_rom_directory(rom_tree["roms"])
        filenames = {r.filename for r in results}
        assert "readme.txt" not in filenames
        assert "notes.md" not in filenames
        assert "gamelist.nfo" not in filenames
        assert "mystery.xyz" not in filenames

    def test_scan_empty_directory(self, tmp_path: Path):
        empty = tmp_path / "empty"
        empty.mkdir()
        assert scan_rom_directory(empty) == []

    def test_scan_nonexistent_directory(self, tmp_path: Path):
        assert scan_rom_directory(tmp_path / "nope") == []

    def test_scan_uppercase_extension_normalized(self, rom_tree):
        results = scan_rom_directory(rom_tree["roms"])
        sonic = next(r for r in results if r.filename == "SONIC.ZIP")
        assert sonic.extension == ".zip"  # lowered


class TestCompatPipeline:
    def test_snes_rom_ok(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "chrono_trigger.sfc")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.OK
        assert report.system == "snes"

    def test_arcade_zip_ok(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "kinst.zip")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.OK
        assert report.system == "arcade"

    def test_n64_missing_core(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "goldeneye.z64")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.MISSING_CORE
        assert report.system == "n64"
        assert report.core_hint == "mupen64plus_next"

    def test_gba_missing_bios(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "metroid_fusion.gba")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.MISSING_BIOS
        assert report.system == "gba"

    def test_cue_without_companion_missing_chd(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "ff7.cue")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.MISSING_CHD
        assert report.system == "psx"

    def test_standalone_bin_ok(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "crash.bin")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.OK
        assert report.system == "psx"

    def test_uppercase_zip_ok(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "SONIC.ZIP")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.OK
        assert report.system == "arcade"

    def test_nested_iso_ok(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "mgs.iso")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert report.status == CompatStatus.OK
        assert report.system == "psx"

    def test_cores_dir_nonexistent_yields_missing_core(self, tmp_path: Path):
        c = next(iter(scan_rom_directory(tmp_path))) if scan_rom_directory(tmp_path) else None
        # Direct construction
        from factory.curator.ingest import RomCandidate
        cand = RomCandidate(path=tmp_path / "x.nes", filename="x.nes", extension=".nes", size_bytes=10)
        report = check_compatibility(cand, tmp_path / "no_cores", tmp_path / "no_bios")
        assert report.status == CompatStatus.MISSING_CORE

    def test_assess_playability_pure_passthrough(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        c = next(c for c in candidates if c.filename == "chrono_trigger.sfc")
        report = check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
        assert assess_playability(report) is report


class TestFullPipelineRun:
    """Drive the entire pipeline end-to-end and assert aggregate correctness."""

    def test_full_pipeline_status_distribution(self, rom_tree):
        candidates = scan_rom_directory(rom_tree["roms"])
        reports = [
            check_compatibility(c, rom_tree["cores"], rom_tree["bios"])
            for c in candidates
        ]
        statuses = {r.candidate.filename: r.status for r in reports}

        assert statuses["chrono_trigger.sfc"] == CompatStatus.OK
        assert statuses["kinst.zip"] == CompatStatus.OK
        assert statuses["SONIC.ZIP"] == CompatStatus.OK
        assert statuses["crash.bin"] == CompatStatus.OK
        assert statuses["mgs.iso"] == CompatStatus.OK
        assert statuses["goldeneye.z64"] == CompatStatus.MISSING_CORE
        assert statuses["metroid_fusion.gba"] == CompatStatus.MISSING_BIOS
        assert statuses["ff7.cue"] == CompatStatus.MISSING_CHD

        # No false positives — count OKs
        ok_count = sum(1 for r in reports if r.status == CompatStatus.OK)
        assert ok_count == 5

        # No UNKNOWN_SYSTEM — all ingested extensions have mappings
        assert all(r.status != CompatStatus.UNKNOWN_SYSTEM for r in reports)
