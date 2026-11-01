"""The native transport must put a model's declared wire names on the wire (#46)."""
from __future__ import annotations

import json

from mcp.types import TextContent
from pydantic import BaseModel, Field

from factory.mcp_utils.interface import ToolResult, ok
from factory.mcp_utils.runtime.native_v2_dispatch import project_result


class _Schema(BaseModel):
    additional_properties: bool = Field(serialization_alias="additionalProperties")


def test_project_result_serializes_declared_aliases() -> None:
    projected = project_result(ok(_Schema(additional_properties=False)), TextContent)
    wire = json.loads(projected.content[0].text)
    assert wire["data"] == {"additionalProperties": False}
    assert projected.structured_content["data"] == {"additionalProperties": False}
