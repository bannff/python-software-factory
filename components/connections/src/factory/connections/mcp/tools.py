"""Typed Connections MCP tools: list, add, import, update, remove, reload."""
from __future__ import annotations

import json
import os
from typing import Any, Callable

from pydantic import ValidationError

from factory.mcp_utils.interface import (
    ToolResult, deterministic, fail, get_envelope, ok, operational,
)
from factory.mcp_utils.registration import typed_tool

from ..runtime.models import ServerRecord, ServerSpec, ServersDocument, StaleServer
from .contracts import (
    AddServerInput, ImportServersInput, ListServersInput, ReloadInput, ReloadOutput,
    RemoveServerInput, RemovedOutput, ServerOutput, ServerView, ServersOutput,
    UpdateServerInput,
)


def owner_identity(explicit: dict[str, Any] | None) -> tuple[str, str]:
    ambient = get_envelope()
    value = ambient if ambient is not None else explicit
    if not isinstance(value, dict):
        raise ValueError("connections_identity_required")
    tenant, owner = value.get("tenant_id"), value.get("principal_id")
    if not all(isinstance(item, str) and item for item in (tenant, owner)):
        raise ValueError("connections_identity_required")
    return tenant, owner


def view(record: ServerRecord, runtime: Any) -> ServerView:
    spec = record.spec
    mounted = record.name in runtime.mounted()
    return ServerView(
        name=record.name, transport=spec.transport, command=spec.command,
        args=list(spec.args), cwd=spec.cwd, env=dict(spec.env),
        url=spec.url, headers=dict(spec.headers),
        enabled=spec.enabled, mounted=mounted,
        unresolved_env=sorted({
            source for source in (*spec.env.values(), *spec.headers.values())
            if not os.environ.get(source)
        }),
        tools_count=runtime.tool_count(record.name) if mounted else 0,
        revision=record.revision, created_at=record.created_at, updated_at=record.updated_at,
    )


def _result(call: Callable[[], Any]) -> ToolResult[Any]:
    try:
        return ok(call())
    except StaleServer:
        return fail("connections_revision_conflict")
    except (ValidationError, json.JSONDecodeError):
        return fail("connections_document_invalid")
    except ValueError as exc:
        text = str(exc)
        return fail(text if text.startswith("connections_") else "connections_invalid")


def register(mcp: Any, get_runtime: Callable[[], Any]) -> None:
    @typed_tool(mcp)
    @deterministic(input_model=ListServersInput, output_model=ServersOutput)
    def connections_list_servers(envelope: dict | None = None) -> ToolResult[ServersOutput]:
        """List this owner's registered external MCP servers (no secret values)."""
        runtime = get_runtime()
        return _result(lambda: ServersOutput(servers=[
            view(item, runtime) for item in runtime.list(*owner_identity(envelope))
        ]))

    @typed_tool(mcp)
    @operational(input_model=AddServerInput, output_model=ServerOutput, idempotent=False)
    async def connections_add_server(
        name: str, spec: dict, envelope: dict | None = None,
    ) -> ToolResult[ServerOutput]:
        """Register one external MCP server and mount it when enabled."""
        runtime = get_runtime()
        tenant, owner = owner_identity(envelope)
        return await _mount_after(runtime, lambda: runtime.add(
            tenant, owner, name, ServerSpec.model_validate(spec),
        ))

    @typed_tool(mcp)
    @operational(input_model=ImportServersInput, output_model=ServersOutput, idempotent=False)
    async def connections_import_servers(
        document: str, envelope: dict | None = None,
    ) -> ToolResult[ServersOutput]:
        """Import a pasted ``{"mcpServers": {...}}`` JSON document."""
        runtime = get_runtime()
        tenant, owner = owner_identity(envelope)
        try:
            parsed = ServersDocument.model_validate(json.loads(document))
            records = runtime.import_document(tenant, owner, parsed)
        except (ValidationError, json.JSONDecodeError, ValueError, StaleServer):
            return fail("connections_document_invalid")
        for record in records:
            await _try_mount(runtime, record)
        return ok(ServersOutput(servers=[view(item, runtime) for item in records]))

    @typed_tool(mcp)
    @operational(input_model=UpdateServerInput, output_model=ServerOutput)
    async def connections_update_server(
        name: str, spec: dict, expected_revision: int, envelope: dict | None = None,
    ) -> ToolResult[ServerOutput]:
        """Replace a server definition (revision CAS) and remount it."""
        runtime = get_runtime()
        tenant, owner = owner_identity(envelope)
        return await _mount_after(runtime, lambda: runtime.update(
            tenant, owner, name, ServerSpec.model_validate(spec), expected_revision,
        ))

    @typed_tool(mcp)
    @operational(input_model=RemoveServerInput, output_model=RemovedOutput)
    async def connections_remove_server(
        name: str, expected_revision: int, envelope: dict | None = None,
    ) -> ToolResult[RemovedOutput]:
        """Unmount and delete a server (revision CAS)."""
        runtime = get_runtime()
        tenant, owner = owner_identity(envelope)
        outcome = _result(lambda: runtime.remove(tenant, owner, name, expected_revision))
        if outcome.ok:
            await runtime.unmount(name)
            return ok(RemovedOutput(removed=True, name=name))
        return outcome

    @typed_tool(mcp)
    @operational(input_model=ReloadInput, output_model=ReloadOutput, idempotent=False)
    async def connections_reload(envelope: dict | None = None) -> ToolResult[ReloadOutput]:
        """Re-discover every enabled server's tools without a process restart."""
        runtime = get_runtime()
        tenant, owner = owner_identity(envelope)
        outcome = await runtime.reload(tenant, owner)
        return ok(ReloadOutput(outcome={key: str(value) for key, value in outcome.items()}))


async def _mount_after(runtime: Any, write: Callable[[], ServerRecord]) -> ToolResult[Any]:
    outcome = _result(write)
    if not outcome.ok:
        return outcome
    record: ServerRecord = outcome.data
    if record.spec.enabled:
        await _try_mount(runtime, record)
    else:
        await runtime.unmount(record.name)
    return ok(ServerOutput(server=view(record, runtime)))


async def _try_mount(runtime: Any, record: ServerRecord) -> None:
    if not record.spec.enabled:
        return
    try:
        await runtime.mount(record)
    except Exception:  # noqa: BLE001 - registration succeeds; mount state is visible in the view
        await runtime.unmount(record.name)


__all__ = ["owner_identity", "register", "view"]
