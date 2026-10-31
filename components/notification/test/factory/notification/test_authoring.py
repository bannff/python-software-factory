"""Tests for authoring security."""
from __future__ import annotations

import os
import pytest
from pathlib import Path

from factory.notification.authoring import AuthoringRuntime, AuthoringError


def _create_config_dir(tmp_path: Path) -> Path:
    """Create test config directory."""
    cfg = tmp_path / "config"
    (cfg / "channels").mkdir(parents=True)
    (cfg / "templates").mkdir(parents=True)
    return cfg


class TestAuthoringRuntime:
    """Test authoring runtime security."""

    def test_disabled_by_default(self, tmp_path: Path, monkeypatch) -> None:
        """Authoring should be disabled by default."""
        monkeypatch.delenv("NOTIFY_ENABLE_AUTHORING_TOOLS", raising=False)
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        assert runtime.is_enabled() is False

    def test_enabled_via_env_var(self, tmp_path: Path, monkeypatch) -> None:
        """Should enable via environment variable."""
        monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1")
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        assert runtime.is_enabled() is True

    def test_write_blocked_when_disabled(self, tmp_path: Path, monkeypatch) -> None:
        """Should block writes when disabled."""
        monkeypatch.delenv("NOTIFY_ENABLE_AUTHORING_TOOLS", raising=False)
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        with pytest.raises(AuthoringError, match="disabled"):
            runtime.upsert_channel("test", {"type": "console", "config": {}})

    def test_path_traversal_blocked(self, tmp_path: Path, monkeypatch) -> None:
        """Should block path traversal attempts."""
        monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1")
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        with pytest.raises(AuthoringError, match="traversal"):
            runtime.upsert_channel("../../../etc/passwd", {"type": "console", "config": {}})

    def test_validates_config_before_write(self, tmp_path: Path, monkeypatch) -> None:
        """Should validate config with Pydantic before writing."""
        monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1")
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        # Missing required 'type' field
        with pytest.raises(AuthoringError, match="validation"):
            runtime.upsert_channel("test", {"config": {}})

    def test_successful_write(self, tmp_path: Path, monkeypatch) -> None:
        """Should write valid config when enabled."""
        monkeypatch.setenv("NOTIFY_ENABLE_AUTHORING_TOOLS", "1")
        cfg = _create_config_dir(tmp_path)
        runtime = AuthoringRuntime(cfg)
        
        path = runtime.upsert_channel("test-channel", {
            "type": "console",
            "config": {"prefix": "[TEST]"},
            "enabled": True,
        })
        
        assert Path(path).exists()
        assert "test-channel.yaml" in path
