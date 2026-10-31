"""Regression tests for Dataset MCP local-input canonicalization."""
from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.dataset.mcp.operational import register
from factory.dataset.runtime.local_inputs import canonicalize_local_input


def test_absolute_path_and_local_file_uri_have_one_identity(tmp_path) -> None:
    source = tmp_path / "input data.jsonl"
    expected = source.resolve().as_uri()
    localhost_uri = f"file://localhost{source.as_posix()}"
    assert canonicalize_local_input(str(source)) == expected
    assert canonicalize_local_input(source.as_uri()) == expected
    assert canonicalize_local_input(localhost_uri) == expected


@pytest.mark.parametrize(("value", "match"), [
    ("relative.jsonl", "absolute path or local file"),
    ("http://example.com/data.jsonl", "absolute path or local file"),
    ("file://remote/tmp/data.jsonl", "Only local file URIs"),
    ("file:///tmp/data.jsonl?download=1", "Only local file URIs"),
    ("file:///tmp/data.jsonl#fragment", "Only local file URIs"),
    ("file:///tmp/%2e%2e/data.jsonl", "Path traversal"),
])
def test_unsupported_local_input_forms_are_rejected(value: str, match: str) -> None:
    with pytest.raises(ValueError, match=match):
        canonicalize_local_input(value)


def test_mcp_forwards_canonical_uri_before_request_identity(tmp_path, monkeypatch) -> None:
    captured = []

    def submit(request, _root):
        captured.append(request)
        return SimpleNamespace(model_dump=lambda mode: {"job_id": "job-702"})

    monkeypatch.setattr("factory.dataset.mcp.operational.dataset_submit_generation", submit)
    mcp = ToolCatalog("dataset-test")
    register(mcp, tmp_path)
    tool = asyncio.run(mcp.get_tool("dataset_submit_generation"))
    source = tmp_path / "source.jsonl"
    result = tool.fn({
        "recipe_uri": "recipe://local/pass-through@1", "recipe_digest": "a" * 64,
        "context_snapshot_uri": "file:///context", "context_snapshot_digest": "b" * 64,
        "tool_schema_snapshot_uri": "file:///tools", "tool_schema_snapshot_digest": "c" * 64,
        "input_artifact_uris": [str(source)], "input_artifact_digests": ["d" * 64],
        "input_artifact_roles": ["scenario_pack"], "scenario_pack_identity": "pack",
        "scenario_pack_version": "1", "scenario_pack_uri": str(source),
        "scenario_pack_digest": "d" * 64, "generator_adapter": "deterministic",
        "generator_version": "1", "generation_seed": 7,
    }).data.root
    assert result == {"job_id": "job-702"}
    canonical = source.resolve().as_uri()
    assert captured[0].input_artifacts[0].uri == canonical
    assert captured[0].scenario_generation.scenario_pack.uri == canonical
