"""Tests for resolve_runtime_settings (pure layer-merge + type parsing)."""

import pytest

from factory.arcade_config.runtime.settings import (
    RetroArchRuntimeSettings,
    resolve_runtime_settings,
)


class TestOverrideBeatsGlobal:
    """Later cfg layers win over earlier ones."""

    def test_system_overrides_global_shader(self):
        global_cfg = {"video_shader_enable": "false", "video_shader": ""}
        system_cfg = {"video_shader_enable": "true", "video_shader": "/shaders/crt-pi.glslp"}
        result = resolve_runtime_settings(global_cfg, system_cfg)
        assert result.shader_enabled is True
        assert result.shader_name == "crt-pi"

    def test_system_overrides_global_runahead(self):
        global_cfg = {"run_ahead_enabled": "false", "run_ahead_frames": "1"}
        system_cfg = {"run_ahead_enabled": "true", "run_ahead_frames": "3"}
        result = resolve_runtime_settings(global_cfg, system_cfg)
        assert result.run_ahead_enabled is True
        assert result.run_ahead_frames == 3

    def test_global_alone_no_override(self):
        global_cfg = {"run_ahead_enabled": "true", "run_ahead_frames": "2"}
        result = resolve_runtime_settings(global_cfg)
        assert result.run_ahead_enabled is True
        assert result.run_ahead_frames == 2


class TestShaderBasename:
    """shader_name = basename without extension."""

    def test_full_path_extracts_name(self):
        cfg = {"video_shader_enable": "true", "video_shader": "/opt/retropie/configs/all/shaders/crt-pi.glslp"}
        result = resolve_runtime_settings(cfg)
        assert result.shader_name == "crt-pi"

    def test_slangp_extension(self):
        cfg = {"video_shader_enable": "true", "video_shader": "/shaders/my-shader.slangp"}
        result = resolve_runtime_settings(cfg)
        assert result.shader_name == "my-shader"

    def test_empty_shader_path_means_disabled(self):
        cfg = {"video_shader_enable": "true", "video_shader": ""}
        result = resolve_runtime_settings(cfg)
        assert result.shader_enabled is False
        assert result.shader_name == ""


class TestFramesDefault:
    """run_ahead_frames defaults to 1, clamped >= 0."""

    def test_missing_key_defaults_to_1(self):
        result = resolve_runtime_settings({})
        assert result.run_ahead_frames == 1

    def test_explicit_zero(self):
        result = resolve_runtime_settings({"run_ahead_frames": "0"})
        assert result.run_ahead_frames == 0

    def test_negative_clamped_to_zero(self):
        result = resolve_runtime_settings({"run_ahead_frames": "-5"})
        assert result.run_ahead_frames == 0


class TestEmptyShaderDisabled:
    """shader_enabled = False when video_shader is empty even if flag is true."""

    def test_flag_true_empty_path(self):
        cfg = {"video_shader_enable": "true", "video_shader": ""}
        result = resolve_runtime_settings(cfg)
        assert result.shader_enabled is False

    def test_flag_true_whitespace_path(self):
        cfg = {"video_shader_enable": "true", "video_shader": "   "}
        result = resolve_runtime_settings(cfg)
        assert result.shader_enabled is False

    def test_flag_false_valid_path(self):
        cfg = {"video_shader_enable": "false", "video_shader": "/shaders/crt.glslp"}
        result = resolve_runtime_settings(cfg)
        assert result.shader_enabled is False
        assert result.shader_name == ""


class TestCorePassthrough:
    """Core is passed through as-is."""

    def test_core_threaded(self):
        result = resolve_runtime_settings({}, core="lr-snes9x2002")
        assert result.core == "lr-snes9x2002"

    def test_core_defaults_empty(self):
        result = resolve_runtime_settings({})
        assert result.core == ""


class TestRealSnesData:
    """Integration: real SNES override resolves correctly (from spec)."""

    def test_snes_truth(self):
        global_cfg = {
            "run_ahead_enabled": "false",
            "run_ahead_frames": "1",
            "video_shader_enable": "false",
            "video_shader": "",
            "video_smooth": "false",
        }
        snes_cfg = {
            "video_shader_enable": "true",
            "video_shader": "/opt/retropie/configs/all/retroarch/shaders/crt-pi.glslp",
        }
        result = resolve_runtime_settings(global_cfg, snes_cfg, core="lr-snes9x2002")
        assert result.run_ahead_enabled is False
        assert result.run_ahead_frames == 1
        assert result.shader_enabled is True
        assert result.shader_name == "crt-pi"
        assert result.video_smooth is False
        assert result.core == "lr-snes9x2002"
