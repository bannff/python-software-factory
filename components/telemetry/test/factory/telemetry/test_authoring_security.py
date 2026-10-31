from __future__ import annotations

import os
from pathlib import Path

import pytest

from factory.telemetry.authoring import AuthoringManager, authoring_enabled, AuthoringError


def test_authoring_disabled_by_default() -> None:
    os.environ.pop("TELEMETRY_ENABLE_AUTHORING_TOOLS", None)
    assert authoring_enabled({"authoring": {"enabled": False}}) is False


def test_authoring_env_var_enables() -> None:
    os.environ["TELEMETRY_ENABLE_AUTHORING_TOOLS"] = "1"
    try:
        assert authoring_enabled({}) is True
    finally:
        os.environ.pop("TELEMETRY_ENABLE_AUTHORING_TOOLS", None)


def test_traversal_protection(tmp_path: Path) -> None:
    cfg = tmp_path / "config"
    cfg.mkdir()
    mgr = AuthoringManager(cfg)
    with pytest.raises(AuthoringError):
        mgr.read_yaml("exporter", "../escape")
