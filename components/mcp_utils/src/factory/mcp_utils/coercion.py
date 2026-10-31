"""Declarative coercion type aliases for MCP tool arguments.

LLMs driving MCP tools frequently serialize nested object/array arguments as
JSON *strings* instead of native objects. FastMCP validates tool args with
pydantic ``validate_python``, which does NOT parse a JSON string into a dict or
list -- it raises a ``dict_type`` / ``list_type`` error and the call fails.

These aliases attach a ``BeforeValidator`` that ``json.loads`` a ``str`` input
(passing native dict/list through untouched) so a stringified object
auto-recovers, while a genuinely malformed string still fails loudly with a
clear per-argument error rather than being swallowed into a silent default.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Annotated, Any

from pydantic import BeforeValidator


def _loads_if_str(value: Any) -> Any:
    """Parse a JSON string into an object; pass non-strings through.

    A malformed JSON string raises ``json.JSONDecodeError`` (a ``ValueError``),
    which pydantic surfaces as a loud validation error -- never a silent
    default.
    """
    if isinstance(value, str):
        return json.loads(value)
    return value


def _loads_if_str_list(value: Any) -> Any:
    """Parse a JSON string into a list; pass non-strings through."""
    if isinstance(value, str):
        return json.loads(value)
    return value


def _parse_if_iso(value: Any) -> Any:
    """Parse an ISO-8601 string into a datetime; pass non-strings through.

    Strict DTOs reject strings for ``datetime`` fields, yet every MCP argument
    crosses the boundary as JSON text. A malformed string raises ``ValueError``
    and surfaces as a loud per-field validation error.
    """
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return value


JsonObject = Annotated[dict[str, Any], BeforeValidator(_loads_if_str)]
JsonArray = Annotated[list[Any], BeforeValidator(_loads_if_str_list)]
WireDatetime = Annotated[datetime, BeforeValidator(_parse_if_iso)]
