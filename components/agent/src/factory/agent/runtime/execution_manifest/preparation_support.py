"""Preparation-only freezing of mutable Agent behavior."""
from __future__ import annotations

import os
import re
from typing import Any, Literal

from .base import json_object
from .behavior_registry import freeze_local_tool, is_local_tool
from .canonical import canonical_bytes, sha256
from .descriptors import (
    ConversationDescriptor, ModelDescriptor, OutputSchemaDescriptor,
    SkillBundle, SkillFile, ToolDescriptor,
)
from ..skill_store import skill_dir

_TEMPLATE = re.compile(r"\{\{\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*\}\}")
_NON_STREAMING = ("meta.llama", "mistral.", "cohere.", "deepseek.")


def render_text(text: str, context: dict[str, Any]) -> str:
    rendered = _TEMPLATE.sub(
        lambda match: str(context.get(match.group(1), match.group(0))), text,
    )
    missing = sorted(set(_TEMPLATE.findall(rendered)))
    if missing:
        raise ValueError(f"unresolved prompt variables: {missing}")
    return rendered


def freeze_model(model_id: str) -> ModelDescriptor:
    if not model_id:
        raise ValueError("agent model must be concrete")
    if model_id.startswith("ollama/"):
        host = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
        host = host[:-3] if host.endswith("/v1") else host
        return ModelDescriptor(provider="ollama", model_id=model_id[7:], settings={"host": host})
    if model_id.startswith("openai.gpt-5"):
        settings: dict[str, Any] = {
            "region": os.getenv("BEDROCK_MANTLE_REGION", "us-east-2"),
            "reasoning_effort": os.getenv("BEDROCK_MANTLE_REASONING_EFFORT", "medium"),
        }
        if base_url := os.getenv("BEDROCK_MANTLE_BASE_URL"):
            settings["base_url"] = base_url
        return ModelDescriptor(provider="mantle", model_id=model_id, settings=settings)
    bare = model_id.removeprefix("us.").removeprefix("eu.")
    if any(bare.startswith(prefix) for prefix in _NON_STREAMING):
        return ModelDescriptor(provider="bedrock", model_id=model_id, settings={"streaming": False})
    return ModelDescriptor(provider="literal", model_id=model_id, settings={})


def freeze_skills(names: list[str]) -> SkillBundle:
    files: list[SkillFile] = []
    for name in names:
        root = skill_dir(name)
        if root is None:
            raise ValueError(f"unknown skill: {name!r}")
        for path in sorted(item for item in root.rglob("*") if item.is_file()):
            content = path.read_text(encoding="utf-8")
            files.append(SkillFile(
                path=f"{name}/{path.relative_to(root).as_posix()}", content=content,
                digest=sha256(content.encode("utf-8")),
            ))
    digest = sha256(canonical_bytes([item.model_dump(mode="json") for item in files]))
    return SkillBundle(names=tuple(names), files=tuple(files), digest=digest)


def freeze_schema(name: str | None) -> OutputSchemaDescriptor | None:
    if name is None:
        return None
    from factory.agent.runtime.graph_output_models import resolve_output_schema

    schema = json_object(resolve_output_schema(name).model_json_schema())
    return OutputSchemaDescriptor(
        name=name, json_schema=schema, digest=sha256(canonical_bytes(schema)),
    )


def freeze_tools(local: list[str], mode: Literal["inherit", "empty", "explicit"],
                 resolved: list[str] | None, exact: bool) -> ToolDescriptor:
    if len(set(local)) != len(local):
        raise ValueError("local tool descriptors must be unique")
    if resolved is None or len(set(resolved)) != len(resolved):
        raise ValueError("resolved MCP allowlist must be explicit and unique")
    return ToolDescriptor(
        local=tuple(freeze_local_tool(tool) for tool in local), mcp_mode=mode,
        resolved_mcp_allowlist=tuple(resolved), exact_tools=exact,
    )


def partition_tools(names: list[str]) -> tuple[list[str], list[str]]:
    """Separate closed local built-ins from exact MCP tool identifiers."""
    local, mcp = [], []
    for name in names:
        (local if is_local_tool(name) else mcp).append(name)
    return local, mcp


def conversation() -> ConversationDescriptor:
    return ConversationDescriptor(window_size=40, should_truncate_results=True, per_turn=3)


__all__ = [
    "conversation", "freeze_model", "freeze_schema", "freeze_skills",
    "freeze_tools", "partition_tools", "render_text",
]
