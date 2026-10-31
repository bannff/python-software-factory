"""Tests for the squad container entrypoint (mission runner)."""
from __future__ import annotations

import argparse
import json
from types import SimpleNamespace

import pytest
import yaml

from factory.agent.scripts import run_squad as entry


def _args(**kw):
    base = dict(squad_file=None, squad_id=None, config_dir=None, task="do it",
                task_file=None, workspace="/work", status_file=None)
    base.update(kw)
    return argparse.Namespace(**base)


def _squad_yaml(tmp_path):
    cfg = {
        "id": "rust-squad", "kind": "squad", "name": "S",
        "sandbox_profile": "rust-sdk",
        "team": {"kind": "graph", "id": "t", "name": "t",
                 "nodes": [{"id": "w", "type": "agent", "agent_id": "developer"}],
                 "entry_points": ["w"]},
        "toolbelt": {"tools": ["write_file"]},
    }
    path = tmp_path / "squad.yaml"
    path.write_text(yaml.safe_dump(cfg))
    return path


@pytest.mark.asyncio
async def test_runs_from_squad_file_and_writes_status(tmp_path, monkeypatch):
    captured = {}

    async def _fake_prepare(
        config, *, workspace, mcp_url, capability_policy_id, proxy_socket, allow_shell,
    ):
        captured.update(
            id=config.id, workspace=workspace, mcp_url=mcp_url,
            capability_policy_id=capability_policy_id, proxy_socket=proxy_socket,
            allow_shell=allow_shell,
        )

        class _P:
            async def aclose(self): captured["closed"] = True
        return _P()

    async def _fake_run(prepared, task):
        captured["task"] = task
        return SimpleNamespace(status="completed", output="done")

    monkeypatch.setattr(entry, "prepare_squad", _fake_prepare, raising=False)
    monkeypatch.setattr(entry, "run_squad", _fake_run, raising=False)
    # actually patch the names imported inside main()
    import factory.agent.runtime.squad_runner as sr
    monkeypatch.setattr(sr, "prepare_squad", _fake_prepare)
    monkeypatch.setattr(sr, "run_squad", _fake_run)
    monkeypatch.setenv("MCP_PROXY_URL", "http://launch-proxy/mcp/")
    monkeypatch.setenv("MCP_PROXY_SOCKET", "/run/companion-x/mcp.sock")
    monkeypatch.setenv("MCP_POLICY_ID", "workload:launch-1")
    monkeypatch.setenv("SQUAD_ALLOW_SHELL", "1")
    monkeypatch.delenv("MCP_TOKEN", raising=False)

    status = tmp_path / "status.json"
    await entry.main(_args(squad_file=str(_squad_yaml(tmp_path)),
                           workspace=str(tmp_path), status_file=str(status)))

    data = json.loads(status.read_text())
    assert data["status"] == "completed"
    assert data["squad"] == "rust-squad"
    assert captured["mcp_url"].endswith("/mcp/")
    assert captured["capability_policy_id"] == "workload:launch-1"
    assert captured["proxy_socket"] == "/run/companion-x/mcp.sock"
    assert captured["allow_shell"] is True
    assert "token" not in repr(captured).lower()
    assert captured["task"] == "do it" and captured["closed"] is True


@pytest.mark.asyncio
async def test_missing_config_writes_failed_status(tmp_path):
    status = tmp_path / "status.json"
    with pytest.raises(ValueError):
        await entry.main(_args(status_file=str(status)))  # no squad-file/-id
    assert json.loads(status.read_text())["status"] == "failed"
