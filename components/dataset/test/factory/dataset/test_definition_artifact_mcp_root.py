"""Public definition artifacts are bound to the Dataset server storage root."""
from __future__ import annotations

import asyncio
import inspect
import json
from pathlib import Path

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog
import pytest
from pydantic import ValidationError

from factory.dataset.interface import DefinitionArtifact
from factory.dataset.mcp import definitions
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError


def _artifact_json() -> str:
    return json.dumps(DefinitionArtifact(
        schema_name="agent.execution-manifest", schema_version="1.0",
        identity="graph-alpha", version="7", content={"nodes": []},
    ).model_dump(mode="json"))


def _tool(mcp: ToolCatalog, name: str):
    return asyncio.run(mcp.get_tool(name))


def _resolve_payload() -> dict[str, object]:
    return {
        "schema_name": "agent.execution-manifest", "schema_version": "1.0",
        "identity": "graph-alpha", "version": "7",
        "uri": "file:///not-read.json", "digest": "a" * 64, "size_bytes": 1,
    }


@pytest.mark.parametrize("name,expected", [
    ("dataset_publish_definition_artifact", {"artifact_json"}),
    ("dataset_resolve_definition_artifact", set(_resolve_payload())),
])
def test_public_contract_omits_storage_root(
    tmp_path: Path, name: str, expected: set[str],
) -> None:
    mcp = ToolCatalog("definition-root-contract")
    definitions.register(mcp, tmp_path / "configured", max_size_bytes=4096)
    tool = _tool(mcp, name)
    assert set(tool.fn._mcp_input_model.model_fields) == expected
    assert "storage_root" not in inspect.signature(tool.fn).parameters
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    assert set(schema["properties"]) == expected
    assert schema["additionalProperties"] is False


@pytest.mark.parametrize("name,runtime_name,payload", [
    ("dataset_publish_definition_artifact", "dataset_publish_definition_artifact",
     {"artifact_json": _artifact_json()}),
    ("dataset_resolve_definition_artifact", "dataset_resolve_definition_artifact",
     _resolve_payload()),
])
def test_storage_root_input_is_rejected_before_runtime_or_filesystem_effect(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    name: str, runtime_name: str, payload: dict[str, object],
) -> None:
    configured = tmp_path / "configured"
    attempted = tmp_path / "attempted"
    monkeypatch.setattr(
        definitions, runtime_name,
        lambda *_args: (_ for _ in ()).throw(AssertionError("runtime called")),
    )
    mcp = ToolCatalog("definition-root-rejection")
    definitions.register(mcp, configured, max_size_bytes=4096)
    with pytest.raises((SchemaMigrationError, ValidationError)):
        _tool(mcp, name).fn({**payload, "storage_root": str(attempted)})
    assert not configured.exists()
    assert not attempted.exists()


def test_publish_and_resolve_use_registered_storage_root(tmp_path: Path) -> None:
    configured = tmp_path / "configured"
    mcp = ToolCatalog("definition-root-selection")
    definitions.register(mcp, configured, max_size_bytes=4096)
    publish = _tool(mcp, "dataset_publish_definition_artifact").fn
    resolve = _tool(mcp, "dataset_resolve_definition_artifact").fn
    published = publish({"artifact_json": _artifact_json()})
    expected = configured.resolve() / (
        "definition_artifacts/identities/graph-alpha/7.json"
    )
    assert Path(published.data.ref.uri.removeprefix("file://")) == expected
    assert expected.is_file()
    resolved = resolve(published.data.ref.model_dump(mode="json"))
    assert resolved.data.content == {"nodes": []}
