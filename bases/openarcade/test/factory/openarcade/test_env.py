"""env.py resolution tests — all three priority layers + the $HOME rejection."""

from __future__ import annotations

import os
from pathlib import Path

import pytest

from factory.openarcade.env import (
    DEFAULT_NCI_HOST,
    DEFAULT_NCI_PORT,
    resolve_config_dir,
    resolve_nci_target,
)


def test_config_dir_cli_wins(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("OPENARCADE_CONFIG_DIR", str(tmp_path / "from_env"))
    chosen = tmp_path / "from_cli"
    assert resolve_config_dir(chosen) == chosen.resolve()


def test_config_dir_env_layer(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENARCADE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENARCADE_CONFIG_DIR", str(tmp_path / "from_env"))
    assert resolve_config_dir(None) == (tmp_path / "from_env").resolve()


def test_config_dir_default(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.delenv("OPENARCADE_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    assert resolve_config_dir(None) == (tmp_path / "openarcade_config").resolve()


def test_config_dir_rejects_home(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="must not live under"):
        resolve_config_dir(tmp_path / "under_home" / "config")


def test_nci_target_cli_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENARCADE_NCI_HOST", "10.0.0.99")
    monkeypatch.setenv("OPENARCADE_NCI_PORT", "9999")
    assert resolve_nci_target("10.0.0.1", 1111) == ("10.0.0.1", 1111)


def test_nci_target_env_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OPENARCADE_NCI_HOST", "10.0.0.42")
    monkeypatch.setenv("OPENARCADE_NCI_PORT", "6000")
    assert resolve_nci_target(None, None) == ("10.0.0.42", 6000)


def test_nci_target_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("OPENARCADE_NCI_HOST", raising=False)
    monkeypatch.delenv("OPENARCADE_NCI_PORT", raising=False)
    assert resolve_nci_target(None, None) == (DEFAULT_NCI_HOST, DEFAULT_NCI_PORT)


def test_nci_target_rejects_bad_port() -> None:
    with pytest.raises(ValueError, match="must be an integer"):
        resolve_nci_target(None, "not-a-port")


def test_nci_target_rejects_out_of_range() -> None:
    with pytest.raises(ValueError, match="out of range"):
        resolve_nci_target(None, 70000)
