"""evals_record_run coerces stringified nested-object args (bd python-factory-38veu).

LLMs driving the MCP tool sometimes serialize nested object arguments (e.g.
``summary``) as JSON *strings*. These tests prove the JsonObject/JsonArray
coercion recovers a stringified object to match the dict path, and that a
genuinely malformed string still fails loudly instead of dropping the record.
"""
from __future__ import annotations

import asyncio
import json
from unittest.mock import patch

from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.evals.mcp.run_record_tools import register


def _kwargs(**extra):
    return {
        "run_id": "run-1", "experiment_name": "exp", "verdict": "PASS",
        "pass_rate": 1.0, "avg_score": 1.0, "total_cases": 1, "passed": 1,
        "case_results": [{"passed": True, "score": 1.0}],
        "case_scores": [1.0], **extra,
    }


def _tool(invoker):
    mcp = ToolCatalog("records")
    register(mcp)
    tool = asyncio.run(mcp.get_tool("evals_record_run"))
    return lambda **kwargs: tool.fn(**kwargs).model_dump(mode="json")


def _store():
    documents: dict[str, dict] = {}

    def invoker(tool: str, **kwargs):
        if tool == "storage_doc_get":
            document = documents.get(kwargs["doc_id"])
            return {"data": document, "id": kwargs["doc_id"]} if document else {}
        assert tool == "storage_doc_create_or_match"
        document = documents.get(kwargs["doc_id"])
        if document is None:
            documents[kwargs["doc_id"]] = kwargs["data"]
            return {"status": "created"}
        existing_hash = document["content_hash"]
        return {
            "status": "matched" if existing_hash == kwargs["content_hash"] else "conflict",
            "existing_content_hash": existing_hash,
        }

    return documents, invoker


def test_summary_json_string_matches_dict_path_and_persists() -> None:
    summary = {"total_cases": 1, "passed": 1, "pass_rate": 1.0}
    docs_dict, invoker_dict = _store()
    docs_str, invoker_str = _store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker_dict}):
        as_dict = _tool(invoker_dict)(**_kwargs(summary=summary, timestamp="fixed"))
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker_str}):
        as_str = _tool(invoker_str)(**_kwargs(summary=json.dumps(summary), timestamp="fixed"))

    assert as_str["ok"] is True
    assert as_dict["ok"] is True
    assert as_str["data"]["persisted"] is True
    assert as_str["data"]["status"] == "created"
    assert docs_str["eval-v2-run-1"]["summary"] == summary
    # Byte-identical durable record: coerced string is indistinguishable from dict.
    assert as_str["data"]["content_hash"] == as_dict["data"]["content_hash"]


def test_malformed_summary_string_fails_loudly() -> None:
    _, invoker = _store()
    with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
        record = _tool(invoker)
        try:
            record(**_kwargs(summary="{not valid json"))
        except Exception:
            return
    raise AssertionError("malformed summary string must raise loudly, not persist a default")
