"""Tests for arcade_config brick — model construction and defaults."""

from pathlib import Path

from factory.arcade_config.interface import ArcadeConfig, SystemCoreMapping


def test_default_config():
    cfg = ArcadeConfig()
    assert cfg.nci_host == "127.0.0.1"
    assert cfg.nci_port == 55355
    assert cfg.system_cores == ()


def test_config_with_core_mappings():
    mapping = SystemCoreMapping(system="arcade", core_path=Path("/cores/mame_libretro.so"))
    cfg = ArcadeConfig(system_cores=(mapping,))
    assert len(cfg.system_cores) == 1
    assert cfg.system_cores[0].system == "arcade"


def test_config_is_frozen():
    cfg = ArcadeConfig()
    try:
        cfg.nci_port = 9999  # type: ignore
        assert False, "Should be frozen"
    except Exception:
        pass
