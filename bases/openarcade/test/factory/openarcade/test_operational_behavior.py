"""Behavioral tests for the openarcade base's MCP tools.

The contract tests verify that tools are registered and return well-shaped
payloads. These tests verify the actual behavior — scan_roms walks the path,
launch validates inputs, run_wall spawns and reports liveness, etc.
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

import pytest

from factory.openarcade import env as _env  # noqa: F401


@pytest.fixture
def env_setup(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    cfg_dir = tmp_path / "cfg"
    home_dir.mkdir()
    monkeypatch.setenv("HOME", str(home_dir))
    monkeypatch.setenv("OPENARCADE_CONFIG_DIR", str(cfg_dir))
    monkeypatch.setenv("OPENARCADE_NCI_HOST", "127.0.0.1")
    monkeypatch.setenv("OPENARCADE_NCI_PORT", "55355")
    from factory.openarcade.server import create_mcp_server

    return create_mcp_server(), cfg_dir


def _fn(mcp, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


class TestScanRoms:

    def test_rejects_system_paths(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_scan_roms")("/proc")
        assert result["error"]
        assert result["count"] == 0
        assert "candidates" in result

    def test_rejects_nonexistent_path(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_scan_roms")("/nonexistent/path/xyz")
        assert result["error"]
        assert result["count"] == 0

    def test_scans_empty_dir(self, env_setup, tmp_path) -> None:
        mcp, _ = env_setup
        target = tmp_path / "empty_roms"
        target.mkdir(parents=True, exist_ok=True)
        result = _fn(mcp, "openarcade_scan_roms")(str(target.resolve()))
        assert result["count"] == 0
        assert result["candidates"] == []
        assert "report_path" in result
        report = json.loads(Path(result["report_path"]).read_text())
        assert report["count"] == 0

    def test_scans_finds_files(self, env_setup, tmp_path) -> None:
        mcp, _ = env_setup
        target = tmp_path / "roms"
        target.mkdir(parents=True, exist_ok=True)
        (target / "game1.nes").write_bytes(b"x" * 1024)
        (target / "game2.gb").write_bytes(b"y" * 2048)
        (target / "ignored.txt").write_bytes(b"not a rom")
        target_resolved = str(target.resolve())
        result = _fn(mcp, "openarcade_scan_roms")(target_resolved)
        assert result["count"] == 2, f"expected 2 ROMs, got {result['count']}"
        for cand in result["candidates"]:
            assert "path" in cand
            assert "filename" in cand
            assert "extension" in cand
            assert "size_bytes" in cand
        report = json.loads(Path(result["report_path"]).read_text())
        assert report["count"] == 2

    def test_report_permissions(self, env_setup, tmp_path) -> None:
        mcp, _ = env_setup
        target = tmp_path / "roms"
        target.mkdir(parents=True, exist_ok=True)
        (target / "game.rom").write_bytes(b"x")
        result = _fn(mcp, "openarcade_scan_roms")(str(target.resolve()))
        report_path = Path(result["report_path"])
        mode = report_path.stat().st_mode & 0o777
        assert mode == 0o640, f"scan_report.json has mode {oct(mode)}, expected 0o640"


class TestLaunch:

    def test_rejects_invalid_game_id(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_launch")("invalid game id with spaces!")
        assert result["state"] == "INVALID"
        assert "error" in result

    def test_rejects_too_long_game_id(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_launch")("a" * 100)
        assert result["state"] == "INVALID"

    def test_blocks_aws_metadata_via_tool_param(self, env_setup) -> None:
        """Regression: agent-supplied nci_host must be SSRF-validated too, not just the env-var path."""
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_launch")("contra", nci_host="169.254.169.254")
        assert result["state"] == "BLOCKED_TARGET"
        assert "blocked range" in result["error"]

    def test_blocks_link_local_via_tool_param(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_launch")("contra", nci_host="169.254.1.1")
        assert result["state"] == "BLOCKED_TARGET"

    def test_blocks_out_of_range_port_via_tool_param(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_launch")("contra", nci_port=99999)
        assert result["state"] == "INVALID_PORT"

    def test_falsy_zero_port_raises(self) -> None:
        """Regression for H2: ``nci_port=0`` must NOT fall through; it raises.

        The old ``nci_port or runtime.nci_port`` pattern would let 0 silently
        become the default. The new env.py catches 0 as out-of-range so the
        misconfiguration surfaces immediately.
        """
        from factory.openarcade.env import resolve_nci_target

        with pytest.raises(ValueError, match="out of range"):
            resolve_nci_target("10.0.0.5", 0)

    def test_explicit_none_uses_default(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        host, port = resolve_nci_target("10.0.0.5", None)
        assert host == "10.0.0.5"
        assert port == 55355  # default


class TestCheckCompatibility:

    def test_rejects_system_path(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_check_compatibility")("/proc/cmdline")
        assert result["status"] == "INVALID_PATH"
        assert "error" in result

    def test_rejects_nonexistent(self, env_setup) -> None:
        mcp, _ = env_setup
        result = _fn(mcp, "openarcade_check_compatibility")("/nonexistent.rom")
        assert result["status"] == "INVALID_PATH"
        assert "error" in result

    def test_unknown_when_no_cores_dir(self, env_setup, tmp_path) -> None:
        mcp, _ = env_setup
        rom = tmp_path / "test.rom"
        rom.write_bytes(b"x" * 1024)
        result = _fn(mcp, "openarcade_check_compatibility")(str(rom.resolve()))
        assert result["rom_path"] == str(rom.resolve())
        assert result["playable"] is False


class TestRunWall:

    def test_returns_pid_and_started(self, env_setup, monkeypatch) -> None:
        mcp, cfg_dir = env_setup

        class _FakeProc:
            pid = 99999
            returncode = None

            def poll(self):
                return None

        def fake_popen(*args, **kwargs):
            return _FakeProc()

        import factory.openarcade.mcp.operational as op_mod

        monkeypatch.setattr(op_mod.subprocess, "Popen", fake_popen)
        result = _fn(mcp, "openarcade_run_wall")()
        assert result["pid"] == 99999
        assert result["wall_started"] is True
        assert (cfg_dir / "wall.pid").read_text() == "99999"

    def test_env_is_safelist(self, env_setup, monkeypatch) -> None:
        mcp, _ = env_setup
        captured: dict = {}

        class _FakeProc:
            pid = 1
            returncode = None

            def poll(self):
                return None

        def fake_popen(*args, **kwargs):
            captured["env"] = kwargs.get("env", {})
            return _FakeProc()

        import factory.openarcade.mcp.operational as op_mod

        monkeypatch.setattr(op_mod.subprocess, "Popen", fake_popen)
        monkeypatch.setenv("AWS_ACCESS_KEY_ID", "AKIA-LEAKED")
        monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "SECRET-LEAKED")
        monkeypatch.setenv("GITHUB_TOKEN", "ghp_LEAKED")
        _fn(mcp, "openarcade_run_wall")()
        env = captured["env"]
        assert "AWS_ACCESS_KEY_ID" not in env, "AWS creds leaked to wall env"
        assert "AWS_SECRET_ACCESS_KEY" not in env
        assert "GITHUB_TOKEN" not in env
        assert env["OPENARCADE_CONFIG_DIR"]

    def test_handles_popen_failure(self, env_setup, monkeypatch) -> None:
        mcp, _ = env_setup

        def fake_popen(*args, **kwargs):
            raise OSError("python not found")

        import factory.openarcade.mcp.operational as op_mod

        monkeypatch.setattr(op_mod.subprocess, "Popen", fake_popen)
        result = _fn(mcp, "openarcade_run_wall")()
        assert result["wall_started"] is False
        assert "error" in result

    def test_handles_immediate_exit(self, env_setup, monkeypatch) -> None:
        mcp, _ = env_setup

        class _DeadProc:
            pid = 1
            returncode = 1

            def poll(self):
                return 1

        def fake_popen(*args, **kwargs):
            return _DeadProc()

        import factory.openarcade.mcp.operational as op_mod

        monkeypatch.setattr(op_mod.subprocess, "Popen", fake_popen)
        result = _fn(mcp, "openarcade_run_wall")()
        assert result["wall_started"] is False
        assert "exited" in result["error"].lower()


class TestSSRFGuard:

    def test_blocks_aws_metadata(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        with pytest.raises(ValueError, match="blocked range"):
            resolve_nci_target("169.254.169.254", 80)

    def test_blocks_loopback_aws_metadata(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        with pytest.raises(ValueError, match="blocked range"):
            resolve_nci_target("169.254.0.1", 80)

    def test_allows_loopback(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        host, port = resolve_nci_target("127.0.0.1", 55355)
        assert host == "127.0.0.1"
        assert port == 55355

    def test_allows_real_lan(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        host, port = resolve_nci_target("10.0.0.42", 55355)
        assert host == "10.0.0.42"
        assert port == 55355

    def test_hostname_passes_through(self) -> None:
        from factory.openarcade.env import resolve_nci_target

        host, port = resolve_nci_target("retroarch.local", 55355)
        assert host == "retroarch.local"
