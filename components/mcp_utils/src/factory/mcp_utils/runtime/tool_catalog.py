"""Framework-neutral catalog for brick MCP primitives."""
from __future__ import annotations

import inspect
import json
import re
from typing import Any, Callable

from .catalog_models import (
    CatalogPrompt, CatalogPromptArgument, CatalogResource, CatalogTool,
    PromptContent, PromptMessage, PromptResult, ResourceContent, ResourceResult,
)


class ToolCatalog:
    def __init__(self, name: str) -> None:
        self.name = name
        self._tools: dict[str, CatalogTool] = {}
        self._resources: dict[str, CatalogResource] = {}
        self._prompts: dict[str, CatalogPrompt] = {}

    def tool(
        self, name: str | None = None, *, description: str | None = None,
        telemetry_excluded_argument_fields: frozenset[str] = frozenset(),
        **_: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            public_name = name or fn.__name__
            if public_name in self._tools:
                raise ValueError(f"duplicate tool: {public_name}")
            self._tools[public_name] = CatalogTool(
                public_name, description or _description(fn), fn,
                frozenset(telemetry_excluded_argument_fields),
            )
            return fn
        return register

    def resource(
        self, uri: str, *, name: str | None = None,
        description: str | None = None, mime_type: str = "text/plain", **_: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            if uri in self._resources:
                raise ValueError(f"duplicate resource: {uri}")
            is_template = "{" in uri and "}" in uri
            self._resources[uri] = CatalogResource(
                None if is_template else uri, uri if is_template else None,
                name or fn.__name__, description or _description(fn), fn, mime_type,
            )
            return fn
        return register

    def prompt(
        self, name: str | None = None, *, description: str | None = None, **_: Any,
    ) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
        def register(fn: Callable[..., Any]) -> Callable[..., Any]:
            public_name = name or fn.__name__
            if public_name in self._prompts:
                raise ValueError(f"duplicate prompt: {public_name}")
            arguments = tuple(
                CatalogPromptArgument(
                    item.name, required=item.default is inspect.Parameter.empty,
                ) for item in inspect.signature(fn).parameters.values()
            )
            self._prompts[public_name] = CatalogPrompt(
                public_name, description or _description(fn), arguments, fn,
            )
            return fn
        return register

    def add_tool(self, tool: Any) -> None:
        fn, name = getattr(tool, "fn", None), getattr(tool, "name", None)
        if not callable(fn) or not isinstance(name, str):
            raise TypeError("tool must expose callable fn and string name")
        self._tools[name] = CatalogTool(
            name, str(getattr(tool, "description", "") or ""), fn,
            frozenset(getattr(
                tool, "telemetry_excluded_argument_fields", frozenset(),
            )),
        )

    def tool_map(self) -> dict[str, CatalogTool]:
        return dict(self._tools)

    async def list_tools(self) -> list[CatalogTool]:
        return list(self._tools.values())

    async def get_tool(self, name: str) -> CatalogTool | None:
        return self._tools.get(name)

    async def call_tool(
        self, name: str, arguments: dict[str, Any] | None = None,
    ) -> Any:
        """Invoke one typed tool and return the native MCP-v2 result shape."""
        tool = self._tools.get(name)
        if tool is None:
            raise KeyError(f"unknown tool: {name}")
        from .native_v2_instrumentation import catalog_identity, invoke_native_tool
        brick_name, tool_name = catalog_identity(self.name, name)
        value = await invoke_native_tool(
            brick_name, tool_name, tool.fn, arguments or {},
            excluded_argument_fields=tool.telemetry_excluded_argument_fields,
        )
        from mcp.types import CallToolResult, TextContent
        structured = (
            value.model_dump(mode="json")
            if hasattr(value, "model_dump") else value
        )
        return CallToolResult(
            content=[TextContent(
                type="text", text=json.dumps(structured, default=str),
            )],
            structured_content=structured,
            is_error=bool(getattr(value, "ok", True) is False),
        )

    async def list_resources(self) -> list[CatalogResource]:
        return [item for item in self._resources.values() if item.uri is not None]

    async def list_resource_templates(self) -> list[CatalogResource]:
        return [item for item in self._resources.values() if item.uri_template is not None]

    async def get_resource(self, uri: str) -> CatalogResource | None:
        if uri in self._resources:
            return self._resources[uri]
        return next((item for item in self._resources.values() if _match(item, uri)), None)

    async def read_resource(self, uri: str) -> ResourceResult:
        resource = await self.get_resource(uri)
        if resource is None:
            raise KeyError(f"unknown resource: {uri}")
        value = resource.fn(**(_match(resource, uri) or {}))
        if inspect.isawaitable(value):
            value = await value
        return ResourceResult((ResourceContent(_content(value), resource.mime_type),))

    async def list_prompts(self) -> list[CatalogPrompt]:
        return list(self._prompts.values())

    async def get_prompt(self, name: str) -> CatalogPrompt | None:
        return self._prompts.get(name)

    async def render_prompt(
        self, name: str, arguments: dict[str, Any] | None = None,
    ) -> PromptResult:
        prompt = await self.get_prompt(name)
        if prompt is None:
            raise KeyError(f"unknown prompt: {name}")
        value = prompt.fn(**(arguments or {}))
        if inspect.isawaitable(value):
            value = await value
        return PromptResult((PromptMessage("user", PromptContent(str(value))),))


def _description(fn: Callable[..., Any]) -> str:
    return (fn.__doc__ or "").strip()


def _content(value: Any) -> str:
    return value if isinstance(value, str) else json.dumps(value, default=str)


def _match(resource: CatalogResource, uri: str) -> dict[str, str] | None:
    template = resource.uri_template
    if template is None:
        return {} if resource.uri == uri else None
    names = re.findall(r"\{([^{}]+)\}", template)
    escaped = re.escape(template).replace(r"\{", "{").replace(r"\}", "}")
    match = re.match("^" + re.sub(r"\{[^{}]+\}", r"([^/]+)", escaped) + "$", uri)
    return dict(zip(names, match.groups())) if match else None


__all__ = ["CatalogPrompt", "CatalogResource", "CatalogTool", "ToolCatalog"]
