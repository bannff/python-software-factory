"""Pure-Python prompt helpers for the UI module.

These expose prompt templates in a test-friendly format without requiring
an MCP server instance.
"""

from __future__ import annotations

from typing import Any

from .mcp.content import PROMPT_TEMPLATES


def list_prompts() -> list[dict[str, Any]]:
    prompts: list[dict[str, Any]] = []
    for name, meta in PROMPT_TEMPLATES.items():
        prompts.append(
            {
                "name": name,
                "description": meta.get("description", ""),
                "arguments": meta.get("arguments", []),
            }
        )
    return prompts


def get_prompt(prompt_name: str, arguments: dict[str, Any] | None = None) -> dict[str, Any]:
    if prompt_name not in PROMPT_TEMPLATES:
        return {"error": f"Unknown prompt: {prompt_name}"}

    arguments = arguments or {}
    template = PROMPT_TEMPLATES[prompt_name]["template"]

    for key, value in arguments.items():
        placeholder = "{" + key + "}"
        if isinstance(value, (list, dict)):
            import json

            value = json.dumps(value, indent=2)
        template = template.replace(placeholder, str(value))

    return {
        "name": prompt_name,
        "messages": [
            {
                "role": "user",
                "content": {"type": "text", "text": template},
            }
        ],
    }
