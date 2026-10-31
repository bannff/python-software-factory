"""MCP resources for openarcade — read-only state under the ``openarcade://`` scheme."""

from __future__ import annotations

import json
import os
from typing import Any, Callable

from factory.mcp_utils.interface import deterministic

from ..env import _SCAN_MAX_REPORT_BYTES
from ..runtime import OpenArcadeRuntime


def _read_scan_report_safe(config_dir: Any) -> dict[str, Any] | None:
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


def register(mcp: Any, get_runtime: Callable[[], OpenArcadeRuntime]) -> None:

    @mcp.resource("openarcade://health")
    @deterministic
    def health() -> dict[str, Any]:
        """Readiness probe — config dir writable, NCI target resolved."""
        runtime = get_runtime()
        config_dir_writable = (
            runtime.config_dir.exists() and os.access(runtime.config_dir, os.W_OK)
        ) or _can_create(runtime.config_dir)
        return {
            "status": "ok" if config_dir_writable else "degraded",
            "config_dir": str(runtime.config_dir),
            "config_dir_writable": config_dir_writable,
            "nci_target": runtime.nci_target,
        }

    @mcp.resource("openarcade://config")
    @deterministic
    def config() -> dict[str, Any]:
        """Resolved env contract."""
        runtime = get_runtime()
        return {
            "config_dir": str(runtime.config_dir),
            "nci_host": runtime.nci_host,
            "nci_port": runtime.nci_port,
            "nci_target": runtime.nci_target,
        }

    @mcp.resource("openarcade://tiles")
    @deterministic
    def tiles() -> dict[str, Any]:
        """Scan report contents, or empty if no scan has run yet."""
        runtime = get_runtime()
        data = _read_scan_report_safe(runtime.config_dir)
        if data is None:
            return {"tiles": [], "count": 0, "note": "no scan report"}
        if "error" in data:
            return {"tiles": [], "count": 0, "error": data["error"]}
        return {
            "tiles": data.get("candidates", []),
            "count": data.get("count", 0),
            "source": str(runtime.config_dir / "scan_report.json"),
        }

    @mcp.resource("openarcade://factory")
    @deterministic
    def factory_meta() -> dict[str, Any]:
        """Self-describing manifest: bricks consumed, tools, resources, prompts."""
        runtime = get_runtime()
        return {
            "name": "openarcade",
            "type": "base",
            "namespace": "factory.openarcade",
            "mcp_server_name": "factory-openarcade",
            "bricks_consumed": ["launch", "library", "arcade_config", "state", "curator", "ui"],
            "tools": [
                "openarcade_get_capabilities",
                "openarcade_health_check",
                "openarcade_describe_config_schema",
                "openarcade_scan_roms",
                "openarcade_launch",
                "openarcade_list_tiles",
                "openarcade_check_compatibility",
                "openarcade_get_config",
                "openarcade_run_wall",
            ],
            "resources": [
                "openarcade://health",
                "openarcade://config",
                "openarcade://tiles",
                "openarcade://factory",
            ],
            "prompts": ["play_game", "scan_rom_directory"],
            "config_dir": str(runtime.config_dir),
            "nci_target": runtime.nci_target,
        }


def _can_create(path: Any) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        return True
    except OSError:
        return False


__all__ = ["register"]
