"""Tests for library brick — model construction and scanner contract."""

from pathlib import Path

from factory.library.interface import Game, StubScanner


def test_game_construction():
    g = Game(id="kinst", title="Killer Instinct", system="arcade", rom_path=Path("/roms/kinst.zip"))
    assert g.id == "kinst"
    assert g.system == "arcade"
    assert g.core_hint is None


def test_game_with_core_hint():
    g = Game(id="ki-gold", title="KI Gold", system="n64", rom_path=Path("/roms/kigold.z64"), core_hint="mupen64plus_next")
    assert g.core_hint == "mupen64plus_next"


def test_game_is_frozen():
    g = Game(id="sf2", title="SF2", system="arcade", rom_path=Path("/roms/sf2.zip"))
    try:
        g.id = "other"  # type: ignore
        assert False, "Should be frozen"
    except Exception:
        pass


def test_stub_scanner_returns_empty():
    scanner = StubScanner()
    result = scanner.scan(Path("/nonexistent"))
    assert result == []
