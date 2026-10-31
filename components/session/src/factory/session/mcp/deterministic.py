"""Deterministic typed MCP tools for the session brick."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, deterministic, ok
from factory.mcp_utils.registration import typed_tool

from .contracts import CapabilitiesOutput, ConfigSchemaOutput, EmptyInput, HealthOutput
from .lifecycle_contracts import (
    ClearableCountOutput, EnvelopeOnlyInput, GetSteerInput, ListSessionsInput,
    SessionOutput, SessionRefInput, SessionsOutput, SteerOutput, SteersOutput,
    ThreadRefInput,
)
from .lifecycle_support import identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=CapabilitiesOutput)
    def session_get_capabilities() -> ToolResult[CapabilitiesOutput]:
        return ok(CapabilitiesOutput.model_validate(get_runtime().get_capabilities()))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=HealthOutput)
    def session_health_check() -> ToolResult[HealthOutput]:
        return ok(HealthOutput.model_validate(get_runtime().health_check()))

    @typed_tool(mcp)
    @deterministic(input_model=EmptyInput, output_model=ConfigSchemaOutput)
    def session_describe_config_schema() -> ToolResult[ConfigSchemaOutput]:
        return ok(ConfigSchemaOutput.model_validate(get_runtime().describe_config_schema()))

    @typed_tool(mcp)
    @deterministic(input_model=SessionRefInput, output_model=SessionOutput)
    def session_get(
        session_id: str, envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime()
        return result(lambda: SessionOutput(
            session=runtime.get_session(
                *identity(runtime.lifecycle, envelope), session_id,
            ),
        ))

    @typed_tool(mcp)
    @deterministic(input_model=ListSessionsInput, output_model=SessionsOutput)
    def session_list(
        include_archived: bool = False,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionsOutput]:
        runtime = get_runtime()
        return result(lambda: SessionsOutput(
            sessions=runtime.list_sessions(
                *identity(runtime.lifecycle, envelope), include_archived=include_archived,
            ),
        ))

    @typed_tool(mcp)
    @deterministic(input_model=GetSteerInput, output_model=SteerOutput)
    def session_get_steer(
        session_id: str, delivery_id: str,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SteerOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SteerOutput(steer=runtime.get_steer(
            *identity(runtime, envelope), session_id, delivery_id,
        )))

    @typed_tool(mcp)
    @deterministic(input_model=ThreadRefInput, output_model=SessionOutput)
    def session_resolve_thread(
        thread_id: str, envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.resolve_thread(
            *identity(runtime, envelope), thread_id,
        )))

    @typed_tool(mcp)
    @deterministic(input_model=SessionRefInput, output_model=SteersOutput)
    def session_list_written_steers(
        session_id: str, envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SteersOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SteersOutput(steers=runtime.list_written(
            *identity(runtime, envelope), session_id,
        )))

    @typed_tool(mcp)
    @deterministic(input_model=EnvelopeOnlyInput, output_model=ClearableCountOutput)
    def session_count_archived(
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[ClearableCountOutput]:
        """Row 8 (feature-map) bulk "Delete all" preview count — upstream's
        ``GET /api/sessions/clearable/count``."""
        runtime = get_runtime().lifecycle
        return result(lambda: ClearableCountOutput(
            count=runtime.count_archived(*identity(runtime, envelope)),
        ))


__all__ = ["register"]
