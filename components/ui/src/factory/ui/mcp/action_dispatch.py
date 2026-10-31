"""ui_dispatch_action — the server-side chokepoint for human view actions."""
from __future__ import annotations

import logging
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, operational

from .action_dispatch_dtos import DispatchActionInput, DispatchActionOutput

if TYPE_CHECKING:
    from ..runtime.runtime import UIRuntime

logger = logging.getLogger(__name__)
_ANON_PRINCIPAL = "local"


def _authorize(brick: str, tool: str, principal: str) -> str | None:
    """Return an authorization refusal, or ``None`` while trusted-local."""
    del brick, tool, principal
    return None


def register(mcp: Any, get_runtime: Callable[[], "UIRuntime"]) -> None:
    """Register the human-action dispatch tool."""
    del get_runtime

    @mcp.tool()
    @operational(input_model=DispatchActionInput, output_model=DispatchActionOutput)
    def ui_dispatch_action(
        action: dict[str, Any], args: dict[str, Any] | None = None,
        thread_id: str | None = None, principal_id: str | None = None,
    ) -> ToolResult[DispatchActionOutput]:
        """Dispatch one human-fired A2UI action through the MCP gateway.

        Invalid actions and target-domain failures remain successful outer
        envelopes because they are normal action outcomes. Invocation failures
        raise so the typed boundary returns a failed outer envelope.
        """
        from factory.mcp_utils.interface import (
            get_service, push_envelope_updates, reset_envelope, set_caller_hint,
        )
        from ..runtime.a2ui import ActionRefError, parse_action_ref
        from ..runtime.a2ui.action_resolve import build_tool_resolver, qualified_name

        resolver = build_tool_resolver()
        try:
            ref = parse_action_ref(action, resolver=resolver)
        except ActionRefError as exc:
            return DispatchActionOutput(ok=False, error=f"Invalid action: {exc}")

        principal = principal_id or _ANON_PRINCIPAL
        refused = _authorize(ref.brick, ref.tool, principal)
        if refused:
            return DispatchActionOutput(ok=False, error=refused)

        local = ref.tool
        if resolver is not None and (probe := resolver(ref.brick, ref.tool)) is not None:
            local = probe[0]
        target = qualified_name(ref.brick, local)
        invoker = get_service("tool_invoker")
        if invoker is None:
            raise RuntimeError("tool_invoker not registered (gateway not initialized)")

        call_args = {**ref.args, **(args or {})}
        env_token = push_envelope_updates(
            principal_id=principal, session_id=thread_id, tool_name=target,
        )
        hint_token = set_caller_hint(f"human:{principal}")
        try:
            result = invoker(target, **call_args)
        except Exception as exc:
            logger.warning("ui_dispatch_action(%s) failed: %s", target, exc)
            raise RuntimeError(f"{type(exc).__name__}: {exc}") from exc
        finally:
            hint_token.var.reset(hint_token)
            reset_envelope(env_token)

        if isinstance(result, dict) and isinstance(result.get("error"), str):
            return DispatchActionOutput(
                ok=False, error=result["error"], tool=target, args=call_args,
            )
        return DispatchActionOutput(
            ok=True, tool=target, args=call_args, result=result,
            invalidates=list(ref.invalidates),
        )
