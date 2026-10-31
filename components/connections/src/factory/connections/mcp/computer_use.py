"""Computer Use readiness as a typed Connections tool (detection only)."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from ..runtime.computer_use import computer_use_status
from .contracts import ComputerUseStatusInput, ComputerUseStatusOutput


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ComputerUseStatusInput, output_model=ComputerUseStatusOutput)
    def connections_computer_use_status() -> ToolResult[ComputerUseStatusOutput]:
        """Is a desktop-automation (computer_*) server mounted, and is the preset runnable here?"""
        status = computer_use_status(get_runtime())
        return ok(ComputerUseStatusOutput(
            platform_supported=status.platform_supported, mounted=status.mounted,
            server_name=status.server_name, tool_names=list(status.tool_names),
            preset_name=status.preset_name, preset_command=status.preset_command,
            preset_args=list(status.preset_args),
            preset_command_found=status.preset_command_found,
            preset_command_path=status.preset_command_path,
            accessibility_hint=status.accessibility_hint,
        ))
