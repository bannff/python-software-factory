"""Brick resource and prompt primitives for neutral catalogs."""
from __future__ import annotations

from typing import Any

from .pools import _run_sync


def get_resources(brick_mcp: Any, brick_name: str) -> dict[str, Any]:
    """List resources and resource templates from a brick."""
    resources = _run_sync(brick_mcp.list_resources())
    templates = _run_sync(brick_mcp.list_resource_templates())
    items = [
        {"uri": str(r.uri), "name": r.name,
         "description": r.description or "", "type": "static"}
        for r in (resources or [])
    ]
    items.extend(
        {"uri_template": str(t.uri_template), "name": t.name,
         "description": t.description or "", "type": "template"}
        for t in (templates or [])
    )
    return {"brick": brick_name, "resources": items, "count": len(items)}


def get_prompts(brick_mcp: Any, brick_name: str) -> dict[str, Any]:
    """List prompts from a brick."""
    prompts = _run_sync(brick_mcp.list_prompts())
    items = [
        {"name": p.name, "description": p.description or "",
         "arguments": [
             {"name": a.name, "description": a.description or "",
              "required": getattr(a, "required", False)}
             for a in (p.arguments or [])
         ]}
        for p in (prompts or [])
    ]
    return {"brick": brick_name, "prompts": items, "count": len(items)}


async def read_resource(
    brick_mcp: Any, uri: str,
) -> dict[str, Any]:
    """Read a resource by URI from a brick."""
    try:
        result = await brick_mcp.read_resource(uri)
        contents = [
            {"content": c.content, "mime_type": getattr(c, "mime_type", "text/plain")}
            for c in (result.contents if result else [])
        ]
        return {"uri": uri, "contents": contents}
    except Exception as e:
        return {"error": f"Failed to read resource '{uri}': {e}"}


async def render_prompt(
    brick_mcp: Any, prompt_name: str,
    arguments: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Render a prompt by name from a brick."""
    try:
        result = await brick_mcp.render_prompt(
            prompt_name, arguments=arguments or {},
        )
        messages = [
            {"role": m.role, "content": m.content.text
             if hasattr(m.content, "text") else str(m.content)}
            for m in (result.messages if result else [])
        ]
        return {"prompt": prompt_name, "messages": messages}
    except Exception as e:
        return {"error": f"Failed to render prompt '{prompt_name}': {e}"}
