"""Extract `tool_name(kw=...)` calls from prose and check them against schemas.

Deliberately small: matches only the tool names it is given, reads top-level
keyword names (not values), and judges them against the strict public input
schema (``additionalProperties: false``).
"""
from __future__ import annotations

import importlib
import re
from dataclasses import dataclass
from pathlib import Path

from factory.mcp_server.runtime.public_admission import project_public_tools

_KW = re.compile(r"\s*([A-Za-z_]\w*)\s*=(?!=)")
_QUOTES = "'\""


@dataclass(frozen=True, slots=True)
class CallProblem:
    path: str
    line: int
    tool: str
    unknown: tuple[str, ...]
    missing: tuple[str, ...]

    def __str__(self) -> str:
        return (f"{self.path}:{self.line} {self.tool} "
                f"unknown={list(self.unknown)} missing={list(self.missing)}")


def public_input_schemas(bricks: tuple[str, ...]) -> dict[str, dict]:
    """Canonical public tool name -> input JSON schema, from live catalogs."""
    maps = [
        (b, importlib.import_module(f"factory.{b}.server").create_tool_catalog().tool_map())
        for b in bricks
    ]
    return {i.public_name: i.input_schema for i in project_public_tools(maps).admitted}


def _args_text(text: str, open_paren: int) -> str | None:
    depth, quote = 0, None
    for i in range(open_paren, len(text)):
        c = text[i]
        if quote:
            quote = None if c == quote else quote
        elif c in _QUOTES:
            quote = c
        elif c == "(":
            depth += 1
        elif c == ")":
            depth -= 1
            if depth == 0:
                return text[open_paren + 1:i]
    return None


def _top_level_keywords(args: str) -> list[str]:
    parts, buf, depth, quote = [], [], 0, None
    for c in args:
        if quote:
            quote = None if c == quote else quote
        elif c in _QUOTES:
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            depth -= 1
        elif c == "," and depth == 0:
            parts.append("".join(buf))
            buf = []
            continue
        buf.append(c)
    parts.append("".join(buf))
    return [m.group(1) for p in parts if (m := _KW.match(p))]


def check_file(
    path: Path, schemas: dict[str, dict], tools: frozenset[str], label: str,
) -> list[CallProblem]:
    text = path.read_text()
    names = "|".join(sorted(tools, key=len, reverse=True))
    pattern = re.compile(r"(?<![\w.])(" + names + r")\(")
    problems: list[CallProblem] = []
    for m in pattern.finditer(text):
        args = _args_text(text, m.end() - 1)
        keywords = _top_level_keywords(args) if args else []
        if not keywords:  # `tool()` or positional prose: nothing to judge
            continue
        schema = schemas[m.group(1)]
        known, required = set(schema.get("properties", {})), set(schema.get("required", []))
        unknown = tuple(k for k in keywords if k not in known)
        missing = tuple(sorted(required - set(keywords)))
        if unknown or missing:
            line = text.count("\n", 0, m.start()) + 1
            problems.append(CallProblem(label, line, m.group(1), unknown, missing))
    return problems
