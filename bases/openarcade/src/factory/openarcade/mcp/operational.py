"""Operational (state-mutating) MCP tools for openarcade."""

from __future__ import annotations

import atexit
import json
import os
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable

from factory.curator.interface import scan_rom_directory
from factory.launch.interface import GetStatusProbe, NciCommand, UdpNciTransport
from factory.mcp_utils.interface import operational

from ..env import _SCAN_MAX_REPORT_BYTES, _validate_nci_host, validate_scan_dir
from ..runtime import OpenArcadeRuntime

_LAUNCH_EXECUTOR = ThreadPoolExecutor(max_workers=2, thread_name_prefix="oa-launch")
atexit.register(_LAUNCH_EXECUTOR.shutdown, wait=False)

_GAME_ID_RE = re.compile(r"^[A-Za-z0-9._\-]{1,64}$")

_WALL_ENV_SAFELIST = frozenset(
    {
        "PATH",
        "HOME",
        "USER",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TERM",
        "SHELL",
        "TZ",
        "LOGNAME",
        "XDG_RUNTIME_DIR",
        "XDG_CONFIG_HOME",
        "OPENARCADE_CONFIG_DIR",
        "OPENARCADE_NCI_HOST",
        "OPENARCADE_NCI_PORT",
        "OPENARCADE_CORES_DIR",
        "OPENARCADE_BIOS_DIR",
        "OPENARCADE_MEDIA_ROOT",
        "OPENARCADE_GAMELIST",
        "OPENARCADE_SYSTEM",
        "OPENARCADE_ROMS_ROOT",
        "OPENARCADE_WEB_PORT",
        "OPENARCADE_NO_FIXTURES",
    }
)


def _validate_game_id(game_id: str) -> str:
    if not _GAME_ID_RE.match(game_id):
        raise ValueError(
            f"game_id must match {_GAME_ID_RE.pattern!r}, got {game_id!r}"
        )
    return game_id


def _safe_wall_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if k in _WALL_ENV_SAFELIST}


def _blocking_launch(
    host: str, port: int, game_id: str, timeout: float
) -> dict[str, Any]:
    transport = UdpNciTransport(host=host, port=port)
    transport.send(NciCommand.LOAD_GAME, payload=game_id)
    probe = GetStatusProbe(transport=transport, timeout=0.5)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = probe.poll()
        if status.state.value == "PLAYING":
            return {
                "game_id": game_id,
                "state": "PLAYING",
                "target": f"{host}:{port}",
            }
        time.sleep(0.1)
    return {
        "game_id": game_id,
        "state": "TIMEOUT",
        "target": f"{host}:{port}",
    }


def _candidate_to_dict(c: Any) -> dict[str, Any]:
    return {
        "path": str(c.path),
        "filename": c.filename,
        "extension": c.extension,
        "size_bytes": c.size_bytes,
    }


def register(mcp: Any, get_runtime: Callable[[], OpenArcadeRuntime]) -> None:

    @mcp.tool(name="openarcade_scan_roms")
    @operational
    def openarcade_scan_roms(rom_dir: str) -> dict[str, Any]:
        """Scan a ROM directory and persist a JSON report under the config dir.

        Refuses to scan ``/proc``, ``/sys``, ``/dev`` or any other system
        directory. Respects ``OPENARCADE_NO_FIXTURES=1``.
        """
        runtime = get_runtime()
        if os.environ.get("OPENARCADE_NO_FIXTURES") == "1":
            print(
                "OPENARCADE_NO_FIXTURES=1: skipping fixture tree",
                file=sys.stderr,
            )
        rom_path = Path(rom_dir).resolve()
        try:
            validate_scan_dir(rom_path)
        except ValueError as exc:
            return {
                "count": 0,
                "candidates": [],
                "report_path": None,
                "error": str(exc),
            }
        candidates = list(scan_rom_directory(rom_path))
        report = {
            "rom_dir": str(rom_path),
            "config_dir": str(runtime.config_dir),
            "count": len(candidates),
            "candidates": [_candidate_to_dict(c) for c in candidates],
        }
        report_path = runtime.config_dir / "scan_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(
            json.dumps(report, indent=2, sort_keys=True, default=str),
            encoding="utf-8",
        )
        try:
            report_path.chmod(0o640)
        except OSError:
            pass
        return {
            "count": report["count"],
            "candidates": report["candidates"],
            "report_path": str(report_path),
        }

    @mcp.tool(name="openarcade_launch")
    @operational
    def openarcade_launch(
        game_id: str,
        nci_host: str | None = None,
        nci_port: int | None = None,
        timeout: float = 5.0,
    ) -> dict[str, Any]:
        """Send an NCI launch command and wait for PLAYING state.

        The blocking UDP send+poll is offloaded to a thread-pool worker so the
        agent's event loop is not stalled for the full ``timeout`` window.
        """
        try:
            game_id = _validate_game_id(game_id)
        except ValueError as exc:
            return {"game_id": game_id, "state": "INVALID", "error": str(exc)}
        runtime = get_runtime()
        host = nci_host if nci_host is not None else runtime.nci_host
        port = nci_port if nci_port is not None else runtime.nci_port
        try:
            host = _validate_nci_host(host)
        except ValueError as exc:
            return {
                "game_id": game_id,
                "state": "BLOCKED_TARGET",
                "error": str(exc),
                "target": f"{host}:{port}",
            }
        if not (0 < port < 65536):
            return {
                "game_id": game_id,
                "state": "INVALID_PORT",
                "error": f"NCI port out of range: {port}",
                "target": f"{host}:{port}",
            }
        try:
            future = _LAUNCH_EXECUTOR.submit(
                _blocking_launch, host, port, game_id, timeout
            )
            return future.result(timeout=timeout + 1.0)
        except RuntimeError as exc:
            return {
                "game_id": game_id,
                "state": "EXECUTOR_SHUTDOWN",
                "error": str(exc),
                "target": f"{host}:{port}",
            }

    @mcp.tool(name="openarcade_run_wall")
    @operational
    def openarcade_run_wall() -> dict[str, Any]:
        """Spawn the Flet wall as a detached subprocess. Returns immediately.

        Only a safelist of env vars is forwarded to the wall process — the
        wall does not need the agent's AWS credentials, API tokens, or other
        secrets, and forwarding them widens the attack surface. Wall stderr
        is captured to ``<config_dir>/wall.log`` so failures are diagnosable
        instead of silently swallowed.
        """
        runtime = get_runtime()
        runtime.config_dir.mkdir(parents=True, exist_ok=True)
        env = _safe_wall_env()
        env["OPENARCADE_CONFIG_DIR"] = str(runtime.config_dir)
        env.setdefault("OPENARCADE_NCI_HOST", runtime.nci_host)
        env.setdefault("OPENARCADE_NCI_PORT", str(runtime.nci_port))
        log_path = runtime.config_dir / "wall.log"
        log_fp = open(log_path, "ab", buffering=0)
        try:
            proc = subprocess.Popen(
                [sys.executable, "-m", "factory.openarcade"],
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=log_fp,
                start_new_session=True,
            )
        except OSError as exc:
            log_fp.close()
            return {
                "pid": None,
                "config_dir": str(runtime.config_dir),
                "wall_started": False,
                "error": f"failed to spawn wall: {exc}",
            }
        time.sleep(0.05)
        if proc.poll() is not None:
            log_fp.close()
            return {
                "pid": proc.pid,
                "config_dir": str(runtime.config_dir),
                "wall_started": False,
                "error": f"wall exited immediately with code {proc.returncode}; see {log_path}",
            }
        pid_file = runtime.config_dir / "wall.pid"
        pid_file.write_text(str(proc.pid), encoding="utf-8")
        try:
            pid_file.chmod(0o640)
        except OSError:
            pass
        log_fp.close()
        return {
            "pid": proc.pid,
            "config_dir": str(runtime.config_dir),
            "wall_started": True,
        }


__all__ = ["register"]
