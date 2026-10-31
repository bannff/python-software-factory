"""Typed SQL storage MCP tools."""
from __future__ import annotations

from typing import Callable, TYPE_CHECKING

from typing import Any
from factory.mcp_utils.interface import ToolResult, operational

from .contracts.base import JsonObject
from .contracts.sql import SqlExecuteOutput, SqlFetchAllOutput, SqlFetchOneOutput, SqlQueryInput, SqlTableExistsInput, SqlTableExistsOutput

if TYPE_CHECKING:
    from ..runtime.runtime import StorageRuntime


def register(mcp: Any, get_runtime: Callable[[], "StorageRuntime"]) -> None:
    """Register SQL storage tools with strict public contracts."""

    @mcp.tool()
    @operational(input_model=SqlQueryInput, output_model=SqlExecuteOutput)
    def sql_execute(query: str, params: JsonObject | None = None) -> ToolResult[SqlExecuteOutput]:
        """Execute a SQL query."""
        result = get_runtime().get_sql_store().execute(query, params)
        return SqlExecuteOutput(rows=result.rows, row_count=result.row_count, columns=result.columns)

    @mcp.tool()
    @operational(input_model=SqlQueryInput, output_model=SqlFetchOneOutput)
    def sql_fetch_one(query: str, params: JsonObject | None = None) -> ToolResult[SqlFetchOneOutput]:
        """Fetch a single row from a SQL query."""
        return SqlFetchOneOutput(row=get_runtime().get_sql_store().fetch_one(query, params))

    @mcp.tool()
    @operational(input_model=SqlQueryInput, output_model=SqlFetchAllOutput)
    def sql_fetch_all(query: str, params: JsonObject | None = None) -> ToolResult[SqlFetchAllOutput]:
        """Fetch all rows from a SQL query."""
        rows = get_runtime().get_sql_store().fetch_all(query, params)
        return SqlFetchAllOutput(rows=rows, count=len(rows))

    @mcp.tool()
    @operational(input_model=SqlTableExistsInput, output_model=SqlTableExistsOutput)
    def sql_table_exists(table_name: str) -> ToolResult[SqlTableExistsOutput]:
        """Check if a SQL table exists."""
        return SqlTableExistsOutput(table=table_name, exists=get_runtime().get_sql_store().table_exists(table_name))
