"""DTOs for Storage SQL MCP tools."""
from __future__ import annotations

from .base import DTO, JsonObject
from pydantic import JsonValue


class SqlQueryInput(DTO):
    query: str
    params: JsonObject | None = None


class SqlExecuteOutput(DTO):
    rows: list[JsonObject]
    row_count: int
    columns: list[str]


class SqlFetchOneOutput(DTO):
    row: JsonObject | None = None


class SqlFetchAllOutput(DTO):
    rows: list[JsonObject]
    count: int


class SqlTableExistsInput(DTO):
    table_name: str


class SqlTableExistsOutput(DTO):
    table: str
    exists: bool
