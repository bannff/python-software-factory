"""Single public admission policy for native MCP-v2 tool declarations."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping

from pydantic import BaseModel

from .name_resolution import canonical_tool_name
from .service_policy import public_tool_map


@dataclass(frozen=True, slots=True)
class AdmittedTool:
    brick: str
    source_name: str
    public_name: str
    tool: Any
    input_schema: dict[str, Any]


@dataclass(frozen=True, slots=True)
class AdmissionProjection:
    admitted: tuple[AdmittedTool, ...]
    invalid_tools: tuple[dict[str, str], ...]


def project_public_tools(
    tool_maps: Iterable[tuple[str, Mapping[str, Any]]],
    *,
    allowlist: set[str] | None = None,
    normalize_dots: bool = True,
) -> AdmissionProjection:
    """Filter service-only first, then admit callable concrete typed tools."""
    candidates: list[AdmittedTool] = []
    invalid: list[dict[str, str]] = []
    for brick, raw_tools in tool_maps:
        for source_name, tool in public_tool_map(raw_tools).items():
            public_name = canonical_tool_name(
                brick, source_name, normalize_dots=normalize_dots,
            )
            if not _selected(allowlist, source_name, public_name):
                continue
            reason, schema = _validate(tool)
            if reason is not None:
                invalid.append(_diagnostic(brick, source_name, public_name, reason))
                continue
            candidates.append(AdmittedTool(
                brick, source_name, public_name, tool, schema or {},
            ))
    admitted = _resolve_collisions(candidates, invalid)
    return AdmissionProjection(
        tuple(sorted(admitted, key=lambda item: item.public_name)),
        tuple(sorted(invalid, key=lambda item: (
            item["public_name"], item["brick"], item["source_name"],
        ))),
    )


def _validate(tool: Any) -> tuple[str | None, dict[str, Any] | None]:
    handler = getattr(tool, "fn", None)
    if not callable(handler):
        return "handler_not_callable", None
    input_model = getattr(handler, "_mcp_input_model", None)
    if not _model_type(input_model):
        return "input_model_not_concrete", None
    output_model = getattr(handler, "_mcp_output_model", None)
    if not _model_type(output_model):
        return "output_model_not_concrete", None
    try:
        schema = input_model.model_json_schema(mode="validation")
    except Exception:
        return "input_schema_generation_failed", None
    if not isinstance(schema, dict) or schema.get("type") != "object":
        return "input_schema_not_object", None
    return None, schema


def _model_type(value: Any) -> bool:
    return isinstance(value, type) and issubclass(value, BaseModel)


def _selected(
    allowlist: set[str] | None, source_name: str, public_name: str,
) -> bool:
    return allowlist is None or source_name in allowlist or public_name in allowlist


def _resolve_collisions(
    candidates: list[AdmittedTool], invalid: list[dict[str, str]],
) -> list[AdmittedTool]:
    grouped: dict[str, list[AdmittedTool]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.public_name, []).append(candidate)
    admitted: list[AdmittedTool] = []
    for public_name, group in grouped.items():
        handlers = {id(getattr(item.tool, "fn", None)) for item in group}
        if len(handlers) == 1:
            admitted.append(_preferred(group))
            continue
        for item in group:
            invalid.append(_diagnostic(
                item.brick, item.source_name, public_name,
                "canonical_name_collision",
            ))
    return admitted


def _preferred(group: list[AdmittedTool]) -> AdmittedTool:
    return sorted(group, key=lambda item: ("." in item.source_name, item.source_name))[0]


def _diagnostic(
    brick: str, source_name: str, public_name: str, reason: str,
) -> dict[str, str]:
    return {
        "brick": brick, "source_name": source_name,
        "public_name": public_name, "reason": reason,
    }


__all__ = [
    "AdmissionProjection", "AdmittedTool", "project_public_tools",
]
