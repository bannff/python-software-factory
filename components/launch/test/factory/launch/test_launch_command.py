"""Tests for launch_command — pure command builder + platform argv."""

import pytest
from unittest.mock import patch

from factory.launch.runtime.launch_command import (
    LaunchConfig,
    build_launch_argv,
    build_override_cfg_text,
    platform_launch_argv,
    is_darwin_trampoline,
)


class TestLaunchConfig:
    """LaunchConfig requires core (non-optional — illegal state unrepresentable)."""

    def test_construct_requires_core(self):
        with pytest.raises(TypeError):
            LaunchConfig(rom="/path/to/game.smc")  # type: ignore[call-arg]

    def test_construct_requires_rom(self):
        with pytest.raises(TypeError):
            LaunchConfig(core="lr-snes9x2002")  # type: ignore[call-arg]

    def test_defaults(self):
        cfg = LaunchConfig(core="/cores/snes9x_libretro.dylib", rom="/roms/game.smc")
        assert cfg.retroarch_bin == "retroarch"
        assert cfg.port == 55355
        assert cfg.video_driver is None


class TestBuildLaunchArgv:
    """build_launch_argv produces [bin, -L, core, rom, --appendconfig, cfg_path]."""

    def test_produces_correct_argv(self):
        cfg = LaunchConfig(
            core="/cores/snes9x_libretro.so",
            rom="/roms/game.smc",
            retroarch_bin="/usr/bin/retroarch",
        )
        argv = build_launch_argv(cfg, "/tmp/override.cfg")
        assert argv == [
            "/usr/bin/retroarch",
            "-L",
            "/cores/snes9x_libretro.so",
            "/roms/game.smc",
            "--appendconfig",
            "/tmp/override.cfg",
        ]

    def test_path_object_cfg_path(self):
        from pathlib import Path
        cfg = LaunchConfig(core="core", rom="rom")
        argv = build_launch_argv(cfg, Path("/tmp/test.cfg"))
        assert argv[-1] == "/tmp/test.cfg"


class TestBuildOverrideCfgText:
    """build_override_cfg_text includes metal line only when video_driver set."""

    def test_always_includes_network_cmd(self):
        cfg = LaunchConfig(core="core", rom="rom", port=55355)
        text = build_override_cfg_text(cfg)
        assert 'network_cmd_enable = "true"' in text
        assert 'network_cmd_port = "55355"' in text

    def test_no_video_driver_when_none(self):
        cfg = LaunchConfig(core="core", rom="rom", video_driver=None)
        text = build_override_cfg_text(cfg)
        assert "video_driver" not in text

    def test_includes_video_driver_when_set(self):
        cfg = LaunchConfig(core="core", rom="rom", video_driver="metal")
        text = build_override_cfg_text(cfg)
        assert 'video_driver = "metal"' in text


class TestPlatformLaunchArgv:
    """platform_launch_argv wraps with `open -a` on Darwin, raw on Linux."""

    def test_darwin_wraps_open_a(self):
        with patch("factory.launch.runtime.launch_command.platform.system", return_value="Darwin"):
            cfg = LaunchConfig(
                core="/cores/snes9x_libretro.dylib",
                rom="/roms/game.smc",
                retroarch_bin="/Applications/RetroArch.app/Contents/MacOS/RetroArch",
            )
            argv = platform_launch_argv(cfg, "/tmp/c.cfg")
            assert argv[:4] == ["open", "-a", "/Applications/RetroArch.app", "--args"]
            assert "-L" in argv
            assert "/cores/snes9x_libretro.dylib" in argv
            assert "/roms/game.smc" in argv
            assert "--appendconfig" in argv
            # Inner binary NOT in argv (open -a handles it via --args)
            assert "/Applications/RetroArch.app/Contents/MacOS/RetroArch" not in argv

    def test_linux_uses_raw_retroarch(self):
        with patch("factory.launch.runtime.launch_command.platform.system", return_value="Linux"):
            cfg = LaunchConfig(
                core="/cores/snes9x_libretro.so",
                rom="/roms/game.smc",
                retroarch_bin="retroarch",
            )
            argv = platform_launch_argv(cfg, "/tmp/c.cfg")
            assert argv[0] == "retroarch"
            assert "open" not in argv
            assert "-L" in argv

    def test_env_override_retroarch_app(self, monkeypatch):
        monkeypatch.setenv("OPENARCADE_RETROARCH_APP", "/custom/RA.app")
        with patch("factory.launch.runtime.launch_command.platform.system", return_value="Darwin"):
            cfg = LaunchConfig(core="c", rom="r", retroarch_bin="ra")
            argv = platform_launch_argv(cfg, "/tmp/c.cfg")
            assert argv[2] == "/custom/RA.app"


class TestIsDarwinTrampoline:
    """is_darwin_trampoline detects argv[0] ending with 'open'."""

    def test_open_detected(self):
        assert is_darwin_trampoline(["open", "-a", "App", "--args"])

    def test_retroarch_not_detected(self):
        assert not is_darwin_trampoline(["retroarch", "-L", "core", "rom"])

    def test_empty_argv(self):
        assert not is_darwin_trampoline([])

    def test_full_path_open(self):
        assert is_darwin_trampoline(["/usr/bin/open", "-a", "App"])
