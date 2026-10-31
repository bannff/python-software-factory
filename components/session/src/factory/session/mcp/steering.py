"""Operational typed MCP tools for session steering (mailbox delivery).

Split out of ``operational.py`` to keep that file under the 200 LOC ceiling
— steering (send/acknowledge/requeue against the mailbox) is a genuinely
separate concern from session lifecycle mutations (create/rename/archive).
"""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, operational, service_only
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import AcknowledgeSteerInput, SteerInput, SteerOutput
from .lifecycle_support import identity, result
from .events import publish_steer


def _delivery_result(call: Callable[[], SteerOutput]) -> ToolResult[SteerOutput]:
    output = result(call)
    if output.ok and output.data is not None:
        publish_steer(output.data.steer)
    return output


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=SteerInput, output_model=SteerOutput, idempotent=False)
    def session_steer(
        session_id: str, send_id: str, content: str,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SteerOutput]:
        runtime = get_runtime().lifecycle
        return _delivery_result(lambda: SteerOutput(steer=runtime.steer(
            *identity(runtime, envelope), session_id, send_id, content,
        )))

    @typed_tool(mcp)
    @service_only(callers={"agent"}, binding="steer")
    @operational(input_model=AcknowledgeSteerInput, output_model=SteerOutput,
                 idempotent=False)
    def session_acknowledge_steer(
        tenant_id: str, owner_id: str, session_id: str,
        delivery_id: str, revision: int,
    ) -> ToolResult[SteerOutput]:
        runtime = get_runtime().lifecycle
        return _delivery_result(lambda: SteerOutput(steer=runtime.acknowledge(
            tenant_id, owner_id, session_id, delivery_id, revision,
        )))

    @typed_tool(mcp)
    @service_only(callers={"agent"}, binding="steer")
    @operational(input_model=AcknowledgeSteerInput, output_model=SteerOutput,
                 idempotent=False)
    def session_requeue_steer(
        tenant_id: str, owner_id: str, session_id: str,
        delivery_id: str, revision: int,
    ) -> ToolResult[SteerOutput]:
        runtime = get_runtime().lifecycle
        return _delivery_result(lambda: SteerOutput(steer=runtime.requeue(
            tenant_id, owner_id, session_id, delivery_id, revision,
        )))


__all__ = ["register"]
