"""Tests for B18 — RetroArch config control-plane runtime."""

from pathlib import Path

import pytest

from factory.arcade_config.runtime.models import (
    RETROPAD_BUTTONS,
    CoreOption,
    InputRemap,
    RunAheadConfig,
    Scope,
    ShaderPreset,
)
from factory.arcade_config.runtime.resolver import override_path
from factory.arcade_config.runtime.serializers import (
    serialize_cfg,
    serialize_core_options,
    serialize_remap,
    serialize_shader_ref,
)
from factory.arcade_config.runtime.writer import write_config


# --- models: illegal-state guards ---


class TestCoreOption:
    def test_accepts_allowed_value(self):
        opt = CoreOption(key="region", value="us", allowed=("us", "jp", "eu"))
        assert opt.value == "us"

    def test_rejects_disallowed_value(self):
        with pytest.raises(ValueError, match="not in allowed"):
            CoreOption(key="region", value="mars", allowed=("us", "jp"))


class TestInputRemap:
    def test_accepts_known_button(self):
        remap = InputRemap(retropad_button="a", target="b")
        assert remap.retropad_button == "a"

    def test_rejects_unknown_button(self):
        with pytest.raises(ValueError, match="Unknown RetroPad button"):
            InputRemap(retropad_button="turbo", target="a")

    def test_all_canonical_buttons_accepted(self):
        for btn in RETROPAD_BUTTONS:
            InputRemap(retropad_button=btn, target="a")


class TestRunAheadConfig:
    def test_defaults(self):
        cfg = RunAheadConfig(enabled=True)
        assert cfg.frames == 1

    def test_frozen(self):
        cfg = RunAheadConfig(enabled=False)
        with pytest.raises(AttributeError):
            cfg.enabled = True  # type: ignore


# --- serializers: exact format assertions ---


class TestSerializeCfg:
    def test_basic_pairs(self):
        result = serialize_cfg({"video_fullscreen": "true", "audio_enable": "true"})
        assert result == 'video_fullscreen = "true"\naudio_enable = "true"\n'

    def test_empty(self):
        assert serialize_cfg({}) == ""


class TestSerializeCoreOptions:
    def test_format(self):
        opts = [
            CoreOption(key="snes9x_region", value="auto", allowed=("auto", "ntsc", "pal")),
            CoreOption(key="snes9x_blargg", value="disabled", allowed=("disabled", "s-video")),
        ]
        result = serialize_core_options(opts)
        assert 'snes9x_region = "auto"\n' in result
        assert 'snes9x_blargg = "disabled"\n' in result

    def test_empty(self):
        assert serialize_core_options([]) == ""


class TestSerializeRemap:
    def test_format(self):
        remaps = [
            InputRemap(retropad_button="a", target="b"),
            InputRemap(retropad_button="b", target="a"),
        ]
        result = serialize_remap(remaps)
        assert 'input_player1_a = "b"\n' in result
        assert 'input_player1_b = "a"\n' in result

    def test_empty(self):
        assert serialize_remap([]) == ""


class TestSerializeShaderRef:
    def test_format(self):
        preset = ShaderPreset(path=Path("/shaders/crt-royale.slangp"))
        result = serialize_shader_ref(preset)
        assert 'video_shader_enable = "true"\n' in result
        assert 'video_shader = "/shaders/crt-royale.slangp"\n' in result


# --- resolver: path precedence ---


class TestOverridePath:
    def test_global_scope(self):
        p = override_path(Path("/config"), Scope.GLOBAL, kind="cfg")
        assert p == Path("/config/global.cfg")

    def test_core_scope(self):
        p = override_path(Path("/config"), Scope.CORE, core="snes9x", kind="cfg")
        assert p == Path("/config/snes9x/snes9x.cfg")

    def test_content_dir_scope(self):
        p = override_path(Path("/config"), Scope.CONTENT_DIR, core="snes9x", game="USA", kind="cfg")
        assert p == Path("/config/snes9x/USA.cfg")

    def test_game_scope(self):
        p = override_path(Path("/config"), Scope.GAME, core="snes9x", game="sf2", kind="opt")
        assert p == Path("/config/snes9x/sf2.opt")

    def test_game_differs_from_global(self):
        global_p = override_path(Path("/config"), Scope.GLOBAL, kind="cfg")
        game_p = override_path(Path("/config"), Scope.GAME, core="mame", game="kof", kind="cfg")
        assert global_p != game_p

    def test_core_scope_raises_without_core(self):
        with pytest.raises(ValueError, match="requires 'core'"):
            override_path(Path("/config"), Scope.CORE, kind="cfg")

    def test_game_scope_raises_without_game(self):
        with pytest.raises(ValueError, match="requires 'game'"):
            override_path(Path("/config"), Scope.GAME, core="snes9x", kind="cfg")


# --- writer: side-effect against real filesystem (tmp_path) ---


class TestWriteConfig:
    def test_writes_content(self, tmp_path: Path):
        target = tmp_path / "config" / "snes9x" / "snes9x.cfg"
        content = 'video_fullscreen = "true"\n'
        write_config(target, content)
        assert target.read_text(encoding="utf-8") == content

    def test_creates_parent_dirs(self, tmp_path: Path):
        target = tmp_path / "deep" / "nested" / "dir" / "file.cfg"
        write_config(target, "x")
        assert target.exists()


# --- parse_cfg: symmetric parser ---


class TestParseCfg:
    """parse_cfg is the read-side mirror of serialize_cfg."""

    def test_round_trip_serialize_then_parse(self):
        from factory.arcade_config.runtime.serializers import parse_cfg
        original = {"run_ahead_enabled": "true", "run_ahead_frames": "1"}
        text = serialize_cfg(original)
        assert parse_cfg(text) == original

    def test_skips_comments_and_blanks(self):
        from factory.arcade_config.runtime.serializers import parse_cfg
        text = '# comment\n\nfoo = "bar"\n   \n'
        assert parse_cfg(text) == {"foo": "bar"}

    def test_last_duplicate_key_wins(self):
        from factory.arcade_config.runtime.serializers import parse_cfg
        text = 'k = "first"\nk = "second"\n'
        assert parse_cfg(text) == {"k": "second"}

    def test_empty_input_returns_empty(self):
        from factory.arcade_config.runtime.serializers import parse_cfg
        assert parse_cfg("") == {}
        assert parse_cfg("   \n\n") == {}

    def test_skips_junk_lines(self):
        from factory.arcade_config.runtime.serializers import parse_cfg
        text = 'not a valid line\nfoo = "bar"\n42\n'
        assert parse_cfg(text) == {"foo": "bar"}
