"""Catalog dispatch reports which input fields were rejected, never their values (#31)."""
from __future__ import annotations

import pytest

from factory.mcp_utils.interface import CatalogTool


@pytest.mark.asyncio
async def test_dispatch_invalid_arguments_name_the_fields_but_never_the_values() -> None:
    from pydantic import BaseModel, Field, ValidationError

    from factory.mcp_server.runtime.tool_dispatch import invoke_catalog_tool
    from factory.mcp_utils.interface import SchemaMigrationError

    class Input(BaseModel):
        persona_id: str = Field(min_length=1)
        project: str = Field(min_length=1)

    canary = "invalid-value-canary"

    def reject() -> None:
        try:
            Input.model_validate({"persona_id": "", "project": canary * 200})
        except ValidationError as exc:
            raise SchemaMigrationError(f"Input validation failed: {exc}") from exc

    result = await invoke_catalog_tool(
        CatalogTool("demo_reject", "", reject), "demo", "demo_reject", {},
    )
    assert result == {
        "ok": False,
        "error": {"type": "InvalidArguments", "message": "invalid_arguments: persona_id"},
    }
    assert canary not in repr(result)


@pytest.mark.asyncio
async def test_dispatch_separates_a_denial_from_a_tool_failure() -> None:
    from factory.mcp_server.runtime.tool_dispatch import invoke_catalog_tool

    def denied() -> None:
        raise PermissionError("principal_id missing for tenant-secret")

    def broken() -> None:
        raise RuntimeError("boom")

    run = lambda fn: invoke_catalog_tool(CatalogTool("t", "", fn), "demo", "t", {})  # noqa: E731
    denial, failure = await run(denied), await run(broken)
    assert denial["error"]["message"] == "authorization_denied"
    assert "tenant-secret" not in repr(denial)
    assert failure["error"]["message"] == "tool_execution_failed"
