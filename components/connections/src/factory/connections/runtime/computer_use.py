"""Computer Use = a desktop-automation MCP server mounted through Connections.

Companion-X does not re-implement macOS accessibility FFI. Any server that
exposes ``computer_*`` tools (KiroCrew's ``kirocrew mcp-computer`` shim is the
bundled preset; upstream ``src/kiro_crew/agent.py:1141`` launches it the same
way) is mounted as pseudo-brick ``mcp-<name>`` and every agent reaches it over
the normal MCP rails: the ONE owner approval list, telemetry, and tool scoping.
"""
from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass, field
from typing import Any

TOOL_PREFIX = "computer_"
PRESET_NAME = "computer"
PRESET_COMMAND = "kirocrew"
PRESET_ARGS = ("mcp-computer",)
ACCESSIBILITY_HINT = (
    "macOS grants Accessibility and Screen Recording to the process that drives the "
    "desktop — for the KiroCrew preset that is the KiroCrew app/gateway, which must be "
    "running with Computer Use enabled. System Settings → Privacy & Security."
)


@dataclass(frozen=True)
class ComputerUseStatus:
    platform_supported: bool
    mounted: bool
    server_name: str | None
    tool_names: tuple[str, ...]
    preset_name: str
    preset_command: str
    preset_args: tuple[str, ...]
    preset_command_found: bool
    preset_command_path: str | None
    accessibility_hint: str = ACCESSIBILITY_HINT
    extra: dict[str, Any] = field(default_factory=dict)


def computer_use_status(runtime: Any) -> ComputerUseStatus:
    """Pure detection over the runtime's mounted catalogs; no dialing."""
    server, tools = _find_mounted(runtime)
    path = shutil.which(PRESET_COMMAND)
    return ComputerUseStatus(
        platform_supported=platform.system() == "Darwin",
        mounted=server is not None,
        server_name=server,
        tool_names=tools,
        preset_name=PRESET_NAME,
        preset_command=PRESET_COMMAND,
        preset_args=PRESET_ARGS,
        preset_command_found=path is not None,
        preset_command_path=path,
    )


def _find_mounted(runtime: Any) -> tuple[str | None, tuple[str, ...]]:
    for name in runtime.mounted():
        tools = tuple(t for t in runtime.tool_names(name) if _is_computer_tool(t))
        if tools:
            return name, tools
    return None, ()


def _is_computer_tool(tool_name: str) -> bool:
    # Mounted names are "<server>.computer_click" or bare "computer_click".
    return tool_name.rsplit(".", 1)[-1].startswith(TOOL_PREFIX)


__all__ = ["ComputerUseStatus", "computer_use_status", "PRESET_ARGS", "PRESET_COMMAND", "PRESET_NAME"]
