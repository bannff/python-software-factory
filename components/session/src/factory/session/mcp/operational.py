"""Operational typed MCP tools for session lifecycle mutations."""
from __future__ import annotations

from typing import Any, Callable

from factory.mcp_utils.interface import ToolResult, fail, operational
from factory.mcp_utils.registration import typed_tool

from .lifecycle_contracts import (
    BindProjectInput, CreateSessionInput, EnsureThreadInput, GenerateTitleInput,
    MovePinnedInput, RebindSessionInput, RenameSessionInput, RevisionSessionInput,
    SessionOutput, SetModelInput, SetPinnedInput,
)
from .lifecycle_support import _ERRORS, identity, result


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @operational(input_model=CreateSessionInput, output_model=SessionOutput)
    def session_create(
        title: str, agent_id: str, model: str, mode: str = "",
        workspace: str = "", project: str = "", origin: str = "user",
        crew_id: str = "", memory_scope: str = "",
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.create(
            *identity(runtime, envelope), title, agent_id, model,
            mode, workspace, project, origin, crew_id, memory_scope,
        )))


    @typed_tool(mcp)
    @operational(input_model=EnsureThreadInput, output_model=SessionOutput,
                 idempotent=False)
    def session_ensure_thread(
        thread_id: str, title: str, agent_id: str, model: str,
        mode: str = "", crew_id: str = "", memory_scope: str = "",
        project: str = "",
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.ensure_thread(
            *identity(runtime, envelope), thread_id, title, agent_id, model,
            crew_id, memory_scope, mode, project,
        )))
    @typed_tool(mcp)
    @operational(input_model=BindProjectInput, output_model=SessionOutput)
    def session_bind_project(
        session_id: str, project: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.bind_project(
            *identity(runtime, envelope), session_id, project, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=SetModelInput, output_model=SessionOutput)
    def session_set_model(
        session_id: str, model: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_model(
            *identity(runtime, envelope), session_id, model, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=RebindSessionInput, output_model=SessionOutput)
    def session_rebind(
        session_id: str, agent_id: str, model: str, expected_revision: int,
        crew_id: str = "", memory_scope: str = "",
        project: str | None = None, workspace: str | None = None,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.rebind(
            *identity(runtime, envelope), session_id, crew_id, memory_scope,
            agent_id, model, expected_revision,
            project=project, workspace=workspace,
        )))

    @typed_tool(mcp)
    @operational(input_model=RenameSessionInput, output_model=SessionOutput)
    def session_rename(
        session_id: str, title: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.rename(
            *identity(runtime, envelope), session_id, title, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=GenerateTitleInput, output_model=SessionOutput)
    def session_generate_title(
        session_id: str, excerpt: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        """Row 17 (feature-map) — automatic title generation, the other
        half of manual rename above. The FE supplies a short excerpt (the
        session brick stays free of chat-transcript knowledge); this
        resolves the session's OWN configured model, generates a short
        title, and applies it through the SAME revision-fenced rename()
        every other write in this file uses — no new write path."""
        from factory.session.runtime.title_generation import (
            TitleGenerationError, generate_title,
        )
        runtime = get_runtime().lifecycle
        tenant_id, owner_id = identity(runtime, envelope)
        try:
            session = runtime.get(tenant_id, owner_id, session_id)
        except tuple(_ERRORS) as exc:
            return fail(_ERRORS[type(exc)])
        try:
            title = generate_title(session.model, excerpt)
        except TitleGenerationError:
            return fail("session_title_generation_unavailable")
        return result(lambda: SessionOutput(session=runtime.rename(
            tenant_id, owner_id, session_id, title, expected_revision,
        )))

    def archive_result(
        session_id: str, expected_revision: int,
        envelope: dict[str, Any] | None, archived: bool,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_archived(
            *identity(runtime, envelope), session_id, archived, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=RevisionSessionInput, output_model=SessionOutput)
    def session_archive(
        session_id: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        return archive_result(session_id, expected_revision, envelope, True)

    @typed_tool(mcp)
    @operational(input_model=RevisionSessionInput, output_model=SessionOutput)
    def session_reopen(
        session_id: str, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        return archive_result(session_id, expected_revision, envelope, False)

    @typed_tool(mcp)
    @operational(input_model=SetPinnedInput, output_model=SessionOutput)
    def session_set_pinned(
        session_id: str, pinned: bool, expected_revision: int,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.set_pinned(
            *identity(runtime, envelope), session_id, pinned, expected_revision,
        )))

    @typed_tool(mcp)
    @operational(input_model=MovePinnedInput, output_model=SessionOutput)
    def session_move_pinned(
        session_id: str, expected_revision: int,
        before_session_id: str | None = None,
        envelope: dict[str, Any] | None = None,
    ) -> ToolResult[SessionOutput]:
        runtime = get_runtime().lifecycle
        return result(lambda: SessionOutput(session=runtime.move_pinned(
            *identity(runtime, envelope), session_id,
            before_session_id, expected_revision,
        )))


__all__ = ["register"]
