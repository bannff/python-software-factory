"""Deterministic (read-only / contract) MCP tools for openarcade."""

from __future__ import annotations

import json
import os
import stat
from pathlib import Path
from typing import Any, Callable

from factory.curator.interface import CompatReport, CompatStatus, RomCandidate
from factory.curator.interface import check_compatibility as _check_compat
from factory.mcp_utils.interface import deterministic

from ..env import _SCAN_MAX_REPORT_BYTES, validate_readable_file
from ..runtime import OpenArcadeRuntime

_DECLARED_BRICKS = ["launch", "library", "arcade_config", "state", "curator", "ui"]


def _read_scan_report(config_dir: Path) -> dict[str, Any] | None:
    report = config_dir / "scan_report.json"
    if not report.is_file():
        return None
    try:
        size = report.stat().st_size
    except OSError:
        return None
    if size > _SCAN_MAX_REPORT_BYTES:
        return {
            "error": "scan_report.json too large",
            "size_bytes": size,
            "max_bytes": _SCAN_MAX_REPORT_BYTES,
        }
    try:
        return json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _build_candidate(path: Path) -> RomCandidate | None:
    try:
        stat_result = path.stat()
    except OSError:
        return None
    if not path.is_file():
        return None
    return RomCandidate(
        path=path,
        filename=path.name,
        extension=path.suffix.lower(),
        size_bytes=stat_result.st_size,
    )


def _config_dir_is_writable(path: Path) -> bool:
    if path.exists():
        return os.access(path, os.W_OK)
    try:
        path.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return True


def register(mcp: Any, get_runtime: Callable[[], OpenArcadeRuntime]) -> None:

    @mcp.tool(name="openarcade_get_capabilities")
    @deterministic
    def openarcade_get_capabilities() -> dict[str, Any]:
        """Return machine-readable capabilities for the openarcade base."""
        return {
            "name": "openarcade",
            "type": "base",
            "namespace": "factory.openarcade",
            "mcp_server_name": "factory-openarcade",
            "features": [
                "game_wall_ui",
                "nci_launch_orchestration",
                "rom_library_scanning",
                "compatibility_probing",
                "flet_desktop_window",
                "typer_cli",
            ],
            "bricks_consumed": _DECLARED_BRICKS,
        }

    @mcp.tool(name="openarcade_health_check")
    @deterministic
    def openarcade_health_check() -> dict[str, Any]:
        """Fast readiness probe — verifies the env contract resolves."""
        runtime = get_runtime()
        config_dir_writable = _config_dir_is_writable(runtime.config_dir)
        return {
            "status": "ok" if config_dir_writable else "degraded",
            "config_dir": str(runtime.config_dir),
            "config_dir_writable": config_dir_writable,
            "nci_target": runtime.nci_target,
        }

    @mcp.tool(name="openarcade_describe_config_schema")
    @deterministic
    def openarcade_describe_config_schema() -> dict[str, Any]:
        """Describe the base's public configuration surface."""
        return {
            "type": "object",
            "properties": {
                "config_dir": {
                    "type": "string",
                    "description": "Override OPENARCADE_CONFIG_DIR (CLI: --config-dir).",
                },
                "nci_host": {
                    "type": "string",
                    "description": "Override OPENARCADE_NCI_HOST (CLI: --nci-host).",
                    "default": "127.0.0.1",
                },
                "nci_port": {
                    "type": "integer",
                    "description": "Override OPENARCADE_NCI_PORT (CLI: --nci-port).",
                    "default": 55355,
                },
            },
        }

    @mcp.tool(name="openarcade_list_tiles")
    @deterministic
    def openarcade_list_tiles() -> dict[str, Any]:
        """List ROM candidates from the most recent scan report, if any."""
        runtime = get_runtime()
        report = _read_scan_report(runtime.config_dir)
        if report is None:
            return {
                "tiles": [],
                "count": 0,
                "source": "none",
                "note": "no scan report found; run openarcade_scan_roms first",
            }
        if "error" in report:
            return {"tiles": [], "count": 0, "source": str(runtime.config_dir / "scan_report.json"), "error": report["error"]}
        return {
            "tiles": report.get("candidates", []),
            "count": report.get("count", len(report.get("candidates", []))),
            "source": str(runtime.config_dir / "scan_report.json"),
        }

    @mcp.tool(name="openarcade_check_compatibility")
    @deterministic
    def openarcade_check_compatibility(rom_path: str) -> dict[str, Any]:
        """Pre-flight check: report compat status for a single ROM path.

        Validates the path is under a sane location (not /proc, /sys, /dev)
        and not inside the config dir. The compatibility check itself is
        delegated to ``factory.curator.interface.check_compatibility`` and
        needs ``cores_dir`` / ``bios_dir`` to be discoverable. By default we
        use ``<config_dir>/cores`` and ``<config_dir>/bios``; set
        ``OPENARCADE_CORES_DIR`` / ``OPENARCADE_BIOS_DIR`` to override.
        """
        runtime = get_runtime()
        path = Path(rom_path)
        try:
            validate_readable_file(path)
        except ValueError as exc:
            return {"rom_path": str(path), "status": "INVALID_PATH", "error": str(exc)}
        candidate = _build_candidate(path)
        if candidate is None:
            return {
                "rom_path": str(path),
                "status": "NOT_A_FILE",
                "playable": False,
            }
        cores_dir = Path(
            os.environ.get("OPENARCADE_CORES_DIR", str(runtime.config_dir / "cores"))
        )
        bios_dir = Path(
            os.environ.get("OPENARCADE_BIOS_DIR", str(runtime.config_dir / "bios"))
        )
        if not cores_dir.is_dir() or not bios_dir.is_dir():
            return {
                "rom_path": str(path),
                "status": CompatStatus.UNKNOWN_SYSTEM.value,
                "playable": False,
                "note": f"cores/bios dirs not found ({cores_dir}, {bios_dir})",
            }
        report: CompatReport = _check_compat(candidate, cores_dir, bios_dir)
        return {
            "rom_path": str(path),
            "status": report.status.value,
            "system": report.system,
            "playable": report.status == CompatStatus.OK,
        }

    @mcp.tool(name="openarcade_get_config")
    @deterministic
    def openarcade_get_config() -> dict[str, Any]:
        """Return the resolved runtime env contract."""
        runtime = get_runtime()
        return {
            "config_dir": str(runtime.config_dir),
            "nci_host": runtime.nci_host,
            "nci_port": runtime.nci_port,
            "nci_target": runtime.nci_target,
        }


__all__ = ["register"]


# Suppress unused import warnings; stat is re-exported for callers.
_ = stat
