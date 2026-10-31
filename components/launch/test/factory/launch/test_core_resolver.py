"""Tests for core_resolver — resolve real dylib/so path from system code."""

from pathlib import Path

import pytest

from factory.launch.runtime.core_resolver import resolve_core_path


def test_resolves_installed_core(tmp_path: Path):
    (tmp_path / "snes9x_libretro.dylib").write_text("")
    got = resolve_core_path("snes", cores_dir=tmp_path, ext=".dylib")
    assert got == str(tmp_path / "snes9x_libretro.dylib")


def test_returns_empty_when_file_missing(tmp_path: Path):
    assert resolve_core_path("snes", cores_dir=tmp_path, ext=".dylib") == ""


def test_unknown_system_returns_empty(tmp_path: Path):
    assert resolve_core_path("dreamcast", cores_dir=tmp_path, ext=".dylib") == ""


def test_empty_system_returns_empty(tmp_path: Path):
    assert resolve_core_path("", cores_dir=tmp_path, ext=".dylib") == ""


def test_case_insensitive_system(tmp_path: Path):
    (tmp_path / "snes9x_libretro.so").write_text("")
    assert resolve_core_path("SNES", cores_dir=tmp_path, ext=".so") != ""


def test_env_override_cores_dir(tmp_path: Path, monkeypatch):
    (tmp_path / "snes9x_libretro.so").write_text("")
    monkeypatch.setenv("OPENARCADE_CORES_DIR", str(tmp_path))
    assert resolve_core_path("snes", ext=".so") == str(tmp_path / "snes9x_libretro.so")


def test_custom_stems(tmp_path: Path):
    (tmp_path / "mycore_libretro.dylib").write_text("")
    got = resolve_core_path("custom", cores_dir=tmp_path, ext=".dylib", core_stems={"custom": "mycore"})
    assert got == str(tmp_path / "mycore_libretro.dylib")
