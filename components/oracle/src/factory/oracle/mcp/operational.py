"""Operational MCP tools for the domain-agnostic Oracle brick."""

from __future__ import annotations

from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.registration import typed_tool
from factory.mcp_utils.interface import ToolResult, operational, ok

from .contracts import VerifyFindingInput, VerifyFindingOutput

# bd:rk4hc — ``verify`` joins the closed op-kind set in a parallel change.
try:
    from factory.mcp_utils.interface import op_kind as _op_kind  # type: ignore
except ImportError:  # pragma: no cover - op_kind not yet shipped
    _op_kind = None


if TYPE_CHECKING:
    from ..runtime.runtime import OracleRuntime

_GET_ENTITY = "graph_graph_get_entity"
_SET_STATE = "graph_graph_set_finding_state"


def op_kind(kind: str) -> Callable[[Any], Any]:
    """Apply the real op-kind trait when its closed set accepts ``kind``."""
    def _decorate(fn: Any) -> Any:
        if _op_kind is None:
            return fn
        try:
            return _op_kind(kind)(fn)
        except ValueError:
            return fn
    return _decorate


def _invoker() -> Callable[..., Any] | None:
    """Return the cross-brick MCP tool invoker, or None if unavailable."""
    try:
        from factory.mcp_utils.interface import get_service
        return get_service("tool_invoker")
    except Exception:
        return None


def _fetch_finding(finding_id: str, backend: str) -> dict[str, Any] | None:
    """Fetch a finding's properties from the graph brick by name."""
    invoke = _invoker()
    if invoke is None:
        return None
    result = invoke(_GET_ENTITY, entity_id=finding_id, backend=backend)
    if not result or not result.ok or result.data is None or not result.data.found:
        return None
    if result.data.entity is None:
        return None
    props = dict(result.data.entity.properties)
    props.setdefault("id", result.data.entity.id)
    return props


def _persist_state(finding_id: str, state: str, backend: str) -> bool:
    """Persist the neutral state via the graph brick's atomic write tool."""
    invoke = _invoker()
    if invoke is None:
        return False
    result = invoke(_SET_STATE, finding_id=finding_id, state=state, backend=backend)
    return bool(result and result.ok and result.data and result.data.success)


def register(mcp: Any, get_runtime: Callable[[], "OracleRuntime"]) -> None:
    """Register the operational verification tool with a strict boundary."""

    @typed_tool(mcp)
    @operational(input_model=VerifyFindingInput, output_model=VerifyFindingOutput)
    @op_kind("verify")
    def oracle_verify_finding(
        finding_id: str, domain: str = "", backend: str = "",
    ) -> ToolResult[VerifyFindingOutput]:
        """Verify a finding and persist its neutral outcome by MCP indirection."""
        from ..core import FINDING_STATES

        finding = _fetch_finding(finding_id, backend)
        if finding is None:
            return ok(VerifyFindingOutput(
                success=False,
                finding_id=finding_id,
                persisted=False,
                error=f"finding not found: {finding_id}",
            ))
        outcome = get_runtime().verify(finding, domain)
        state = outcome.get("state")
        persisted = state in FINDING_STATES and _persist_state(finding_id, state, backend)
        return ok(VerifyFindingOutput(
            success=True,
            finding_id=finding_id,
            persisted=persisted,
            state=state,
            evidence=outcome.get("evidence"),
            verifier=outcome.get("verifier"),
            error=outcome.get("error"),
        ))
