"""Typed MCP tools for owner-authored prompts (``agent_*_prompt``).

Authority is ambient (envelope-derived); tools never accept tenant/owner. Authored
prompts are owner-scoped, revision-fenced, and carry ``origin: authored`` so a UI
can list them beside the read-only built-in brick prompts. Failures are typed:
``prompt_exists`` / ``prompt_not_found`` / ``prompt_revision_conflict`` /
``prompt_invalid`` / ``prompt_argument_missing`` / ``prompt_identity_required``.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, TYPE_CHECKING

from factory.mcp_utils.interface import (
    ToolResult, TypedToolFailure, deterministic, fail, get_envelope, ok, operational,
)

from ..runtime.prompt_models import PromptArg, PromptRecord, render
from ..runtime.prompt_store import DiskPromptStore
from .contracts.prompts import (
    PromptAddInput, PromptArgDTO, PromptDeleteInput, PromptDeletedOutput,
    PromptListInput, PromptMessage, PromptOutput, PromptRecordDTO, PromptRenderInput,
    PromptRenderOutput, PromptsOutput, PromptUpdateInput,
)

if TYPE_CHECKING:
    from ..agent import SuperAgent


def _identity() -> tuple[str, str]:
    envelope = get_envelope() or {}
    tenant, owner = envelope.get("tenant_id"), envelope.get("principal_id")
    if not all(isinstance(v, str) and v for v in (tenant, owner)):
        raise TypedToolFailure("prompt_identity_required")
    return tenant, owner


def _run(fn: Callable[[str, str], Any]) -> ToolResult[Any]:
    try:
        return ok(fn(*_identity()))
    except TypedToolFailure as exc:
        return fail(exc.code)


def _args(items: list[PromptArgDTO]) -> tuple[PromptArg, ...]:
    return tuple(PromptArg(**PromptArgDTO.model_validate(item).model_dump()) for item in items)


def _dto(record: PromptRecord) -> PromptRecordDTO:
    return PromptRecordDTO(
        prompt_id=record.prompt_id, description=record.description,
        arguments=[PromptArgDTO(**a.model_dump()) for a in record.arguments],
        template=record.template, revision=record.revision,
        created_at=record.created_at.isoformat(), updated_at=record.updated_at.isoformat(),
    )


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register list/add/update/delete/render tools for authored prompts."""
    cache: list[DiskPromptStore] = []

    def store_() -> DiskPromptStore:
        # Lazy: stand-in agents have no config_dir until a prompt tool is called.
        if not cache:
            cache.append(DiskPromptStore(Path(agent.config_dir) / "prompts"))
        return cache[0]

    @mcp.tool()
    @deterministic(input_model=PromptListInput, output_model=PromptsOutput)
    def agent_list_prompts() -> ToolResult[PromptsOutput]:
        """List the caller's authored prompts."""
        def run(t: str, o: str) -> PromptsOutput:
            records = store_().list(t, o)
            return PromptsOutput(count=len(records), prompts=[_dto(r) for r in records])
        return _run(run)

    @mcp.tool()
    @operational(input_model=PromptAddInput, output_model=PromptOutput)
    def agent_add_prompt(
        prompt_id: str, template: str, description: str = "",
        arguments: list[PromptArgDTO] | None = None,
    ) -> ToolResult[PromptOutput]:
        """Exclusively create an authored prompt at revision 1."""
        return _run(lambda t, o: PromptOutput(prompt=_dto(
            store_().create(t, o, prompt_id, description, _args(arguments or []), template))))

    @mcp.tool()
    @operational(input_model=PromptUpdateInput, output_model=PromptOutput)
    def agent_update_prompt(
        prompt_id: str, expected_revision: int, description: str | None = None,
        arguments: list[PromptArgDTO] | None = None, template: str | None = None,
    ) -> ToolResult[PromptOutput]:
        """Revision-fenced partial update; omitted fields keep their value."""
        return _run(lambda t, o: PromptOutput(prompt=_dto(store_().update(
            t, o, prompt_id, expected_revision, description=description,
            arguments=None if arguments is None else _args(arguments), template=template,
        ))))

    @mcp.tool()
    @operational(input_model=PromptDeleteInput, output_model=PromptDeletedOutput)
    def agent_delete_prompt(prompt_id: str) -> ToolResult[PromptDeletedOutput]:
        """Delete an authored prompt."""
        def run(t: str, o: str) -> PromptDeletedOutput:
            store_().delete(t, o, prompt_id)
            return PromptDeletedOutput(prompt_id=prompt_id, deleted=True)
        return _run(run)

    @mcp.tool()
    @deterministic(input_model=PromptRenderInput, output_model=PromptRenderOutput)
    def agent_render_authored_prompt(
        prompt_id: str, arguments: dict[str, str] | None = None,
    ) -> ToolResult[PromptRenderOutput]:
        """Render an authored prompt; required arguments must be supplied."""
        def run(t: str, o: str) -> PromptRenderOutput:
            text = render(store_().get(t, o, prompt_id), dict(arguments or {}))
            return PromptRenderOutput(
                prompt_id=prompt_id, messages=[PromptMessage(role="user", content=text)],
            )
        return _run(run)


__all__ = ["register"]
