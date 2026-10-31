"""Tests for KB's stable typed ingest MCP contract."""

from __future__ import annotations

import asyncio
from typing import Any
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from factory.kb.models.ingest import KbIngestRequest, KbIngestResult
from factory.mcp_utils.interface import SchemaMigrationError
from factory.mcp_utils.runtime.idempotency import cache_clear
from factory.mcp_utils.runtime.tool_result import ToolResult


class TestKbIngestRequest:
    def test_v1_default(self) -> None:
        request = KbIngestRequest(content="hello world", document_id="doc_1")
        assert request.schema_version == "v1"
        assert request.content == "hello world"

    def test_document_id_pattern_enforced(self) -> None:
        with pytest.raises(ValidationError):
            KbIngestRequest(content="x", document_id="INVALID ID")

    def test_content_min_length(self) -> None:
        with pytest.raises(ValidationError):
            KbIngestRequest(content="")


class TestIngestMcpContract:
    def _tool(self, runtime: Any):
        from factory.kb.mcp.tools.operational import register
        from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

        mcp = ToolCatalog("kb-test")
        register(mcp, lambda: runtime)
        return asyncio.run(mcp.get_tool("ingest"))

    @staticmethod
    def _runtime() -> MagicMock:
        runtime = MagicMock()
        runtime.ingest.return_value = MagicMock(
            document_id="doc_1", status="ok", extraction_status=None,
            entities_created=0, relationships_created=0, extraction_message=None,
        )
        return runtime

    def test_ingest_returns_typed_tool_result(self) -> None:
        tool = self._tool(self._runtime())
        result = tool.fn(content="hello", document_id="doc_1", idempotency_key="k1")
        assert isinstance(result, ToolResult)
        assert result.ok is True
        assert result.idempotency_key == "k1"
        assert isinstance(result.data, KbIngestResult)
        assert result.data.document_id == "doc_1"

    def test_schema_exposes_only_stable_flat_v1_fields(self) -> None:
        tool = self._tool(self._runtime())
        schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
        properties = schema["properties"]
        assert properties["content"]["minLength"] == 1
        assert "pattern" in properties["document_id"]["anyOf"][0]
        assert "body" not in properties
        assert "doc_id" not in properties

    def test_fastmcp_rejects_unpublished_legacy_shape(self) -> None:
        runtime = self._runtime()
        tool = self._tool(runtime)
        with pytest.raises(SchemaMigrationError):
            tool.fn(body="legacy", doc_id="doc_1")
        runtime.ingest.assert_not_called()

    def test_idempotency_replays_same_key(self) -> None:
        cache_clear()
        runtime = self._runtime()
        tool = self._tool(runtime).fn
        first = tool(content="hello", document_id="doc_1", idempotency_key="once", tenant_id="tenant-1")
        replay = tool(content="hello", document_id="doc_1", idempotency_key="once", tenant_id="tenant-1")
        assert first.data.document_id == replay.data.document_id == "doc_1"
        assert runtime.ingest.call_count == 1
        cache_clear()

    def test_successful_ingest_emits_only_explicit_graph_references(self, monkeypatch) -> None:
        from factory.kb.mcp.tools import operational
        runtime = self._runtime()
        runtime.ingest.return_value.status = "ingested"
        seen = []
        monkeypatch.setattr(operational, "emit_kb_projection", lambda *args, **kwargs: seen.append((args, kwargs)))
        tool = self._tool(runtime).fn
        result = tool(
            content="private body", document_id="doc_1",
            tenant_id="tenant", principal_id="owner",
            graph_references=[{
                "kind": "workflow-run", "local_id": "run-1",
                "entity_type": "WorkflowRun", "relation_type": "about_run",
            }],
        )
        assert result.ok and len(seen) == 1
        assert seen[0][0] == ("doc_1",)
        assert seen[0][1]["references"][0]["local_id"] == "run-1"
        assert "private body" not in str(seen)

    def test_graph_references_are_strict(self) -> None:
        with pytest.raises(ValidationError):
            KbIngestRequest(content="x", graph_references=[{
                "kind": "kb", "local_id": "doc", "entity_type": "KBDocument",
                "relation_type": "mentions", "unexpected": True,
            }])
