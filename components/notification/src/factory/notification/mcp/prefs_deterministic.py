"""Deterministic owner-scoped notification preference read tool."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import ToolResult, deterministic
from factory.mcp_utils.registration import typed_tool

from .contracts.prefs_inputs import PreferencesGetInput
from .contracts.prefs_outputs import PreferencesOutput
from .inbox_support import inbox_result

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register preference reads using ambient tenant/owner authority."""

    @typed_tool(mcp)
    @deterministic(input_model=PreferencesGetInput, output_model=PreferencesOutput)
    def get_preferences() -> ToolResult[PreferencesOutput]:
        """Read the caller's delivery preferences or revision-one defaults."""
        PreferencesGetInput.model_validate({})
        return inbox_result(lambda tenant, owner: PreferencesOutput.from_preferences(
            runtime.prefs_get(tenant, owner)))


__all__ = ["register"]
