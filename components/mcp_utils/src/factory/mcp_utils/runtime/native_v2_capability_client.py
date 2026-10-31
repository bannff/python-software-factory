"""In-process public-MCP-v2 adapter for ``ScopedCapabilityClientPort``."""

from __future__ import annotations

from copy import deepcopy
import inspect
from typing import Any

from .elicitation import ElicitationForm, ElicitationHandler, ElicitationResponse
from .native_v2_composer import _supports_public_callbacks
from ..context import envelope_updates_from_mapping, push_envelope_updates, reset_envelope
from .scoped_capabilities import (
    CapabilityDescriptor,
    CapabilityInvocation,
    CapabilityResult,
    CapabilityScope,
)
from .scoped_capability_client import CapabilityAccessError


class NativeV2ScopedCapabilityClient:
    """Scope an in-process public-v2 ``Server`` without another registry."""

    def __init__(
        self,
        server: Any,
        scope: CapabilityScope,
        *,
        elicitation_handler: ElicitationHandler | None = None,
        input_required_max_rounds: int = 1,
        read_timeout_seconds: float | None = None,
    ) -> None:
        self._server = server
        self._scope = CapabilityScope.create(
            scope.policy_id, scope.tool_names,
            delegation_depth=scope.delegation_depth, digest=scope.digest,
        )
        self._elicitation_handler = elicitation_handler
        self._input_required_max_rounds = input_required_max_rounds
        self._read_timeout_seconds = read_timeout_seconds
        self._client: Any | None = None
        self._closed = False

    @property
    def scope(self) -> CapabilityScope:
        """Return the immutable policy bound at construction."""
        return self._scope

    async def list_capabilities(self) -> tuple[CapabilityDescriptor, ...]:
        """Discover through the server, returning only allowlisted tools."""
        tools = await self._client_or_open().list_tools()
        return tuple(
            CapabilityDescriptor(tool.name, tool.description or "", deepcopy(tool.input_schema))
            for tool in sorted(tools.tools, key=lambda item: item.name)
            if tool.name in self._scope.tool_names
        )

    async def invoke(self, request: CapabilityInvocation) -> CapabilityResult:
        """Invoke exactly one allowed native tool with its raw argument mapping."""
        if request.name not in self._scope.tool_names:
            raise CapabilityAccessError(f"capability outside scope: {request.name}")
        updates = envelope_updates_from_mapping(request.correlation)
        token = push_envelope_updates(**updates)
        try:
            client = _new_client(
                self._server,
                elicitation_handler=self._elicitation_handler,
                input_required_max_rounds=self._input_required_max_rounds,
                read_timeout_seconds=self._read_timeout_seconds,
            )
            try:
                result = await client.call_tool(request.name, request.arguments)
            finally:
                await client.__aexit__(None, None, None)
        finally:
            reset_envelope(token)
        from mcp.types import CallToolResult
        if not isinstance(result, CallToolResult):
            raise TypeError("MCP client returned a non-terminal tool result")
        content = tuple(_plain(item) for item in result.content)
        structured = getattr(result, "structured_content", None)
        return CapabilityResult(
            content=content,
            structured_content=None if structured is None else _plain(structured),
            is_error=bool(getattr(result, "is_error", False)),
        )

    async def close(self) -> None:
        """Close the one client session idempotently."""
        if self._closed:
            return
        self._closed = True
        if self._client is not None:
            await self._client.__aexit__(None, None, None)

    def _client_or_open(self) -> Any:
        if self._closed:
            raise CapabilityAccessError("capability client is closed")
        if self._client is None:
            self._client = _new_client(
                self._server,
                elicitation_handler=self._elicitation_handler,
                input_required_max_rounds=self._input_required_max_rounds,
                read_timeout_seconds=self._read_timeout_seconds,
            )
        return self._client


def _new_client(
    server: Any,
    *,
    elicitation_handler: ElicitationHandler | None,
    input_required_max_rounds: int,
    read_timeout_seconds: float | None,
) -> Any:
    """Construct and enter the v2 in-process client through public APIs."""
    try:
        from mcp import Client
        from mcp.server import Server
    except ImportError as exc:  # pragma: no cover - pre-cutover environment
        raise RuntimeError("NativeV2ScopedCapabilityClient requires mcp>=2.1.1") from exc
    if not isinstance(server, Server) or not _supports_public_callbacks(Server):
        raise RuntimeError("NativeV2ScopedCapabilityClient requires a public MCP v2 Server")
    callback = None if elicitation_handler is None else _elicitation_callback(elicitation_handler)
    client = Client(
        server,
        elicitation_callback=callback,
        input_required_max_rounds=input_required_max_rounds,
        read_timeout_seconds=read_timeout_seconds,
    )
    return _EnteredClient(client)


def _elicitation_callback(handler: ElicitationHandler) -> Any:
    """Adapt the SDK form callback without enabling deprecated request types."""
    async def callback(_: Any, params: Any) -> Any:
        from mcp.types import ElicitResult, ErrorData, INVALID_REQUEST

        if getattr(params, "mode", None) != "form":
            return ErrorData(code=INVALID_REQUEST, message="Only form elicitation is supported")
        form = ElicitationForm(params.message, deepcopy(params.requested_schema))
        response = handler(form)
        if inspect.isawaitable(response):
            response = await response
        if not isinstance(response, ElicitationResponse):
            raise TypeError("elicitation handler must return ElicitationResponse")
        content = None if response.content is None else dict(response.content)
        return ElicitResult(action=response.action, content=content)

    return callback


class _EnteredClient:
    """Lazily enter the public client once without exposing lifecycle details."""

    def __init__(self, client: Any) -> None:
        self._client = client
        self._entered = False

    async def list_tools(self) -> Any:
        await self._enter()
        return await self._client.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        await self._enter()
        return await self._client.call_tool(name, arguments)

    async def __aexit__(self, *args: Any) -> None:
        if self._entered:
            await self._client.__aexit__(*args)

    async def _enter(self) -> None:
        if not self._entered:
            await self._client.__aenter__()
            self._entered = True


def _plain(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json", by_alias=True)
    if isinstance(value, dict):
        return {key: _plain(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_plain(item) for item in value]
    return value


__all__ = ["NativeV2ScopedCapabilityClient"]
