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
