"""Operational owner-scoped notification preference update tool."""
from __future__ import annotations

from typing import TYPE_CHECKING, Any

from factory.mcp_utils.interface import ToolResult, operational
from factory.mcp_utils.registration import typed_tool

from .contracts.prefs_inputs import PreferencePriority, PreferencesUpdateInput
from .contracts.prefs_outputs import PreferencesOutput
from .inbox_support import inbox_result
from ..runtime.inbox_models import Priority

if TYPE_CHECKING:
    from ..runtime.dispatcher import NotificationRuntime


def register(mcp: Any, runtime: "NotificationRuntime") -> None:
    """Register full-replace preference writes guarded by revision CAS."""

    @typed_tool(mcp)
    @operational(input_model=PreferencesUpdateInput, output_model=PreferencesOutput)
    def update_preferences(
        global_muted: bool, muted_kinds: list[str],
        priority_overrides: dict[str, PreferencePriority], expected_revision: int,
    ) -> ToolResult[PreferencesOutput]:
        """Replace the caller's delivery preferences iff revision is current."""
        parsed = PreferencesUpdateInput.model_validate({
            "global_muted": global_muted, "muted_kinds": muted_kinds,
            "priority_overrides": priority_overrides,
            "expected_revision": expected_revision,
        })
        return inbox_result(lambda tenant, owner: PreferencesOutput.from_preferences(
            runtime.prefs_update(
                tenant, owner, global_muted=parsed.global_muted,
                muted_kinds=frozenset(parsed.muted_kinds),
                priority_overrides={
                    kind: Priority(value)
                    for kind, value in parsed.priority_overrides.items()
                }, expected_revision=parsed.expected_revision,
            )))


__all__ = ["register"]
