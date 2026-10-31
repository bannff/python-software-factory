"""Tests for the evals_evaluate_can_model MCP tool.

Mirrors the style of test_server.py / test_mcp_contract.py — resolve the
tool via the FastMCP server and call ``tool.fn`` directly.
"""

from __future__ import annotations

import asyncio
import hashlib
import json

from factory.evals.server import get_mcp_server
from factory.evals.runtime.runtime import reset_runtime


def _get_tool(name: str):
    """Get a tool by name from the MCP server."""
    mcp = get_mcp_server()
    return asyncio.run(mcp.get_tool(name))


class TestEvalsEvaluateCanModelTool:
    """Verify the evals_evaluate_can_model MCP tool is registered and works."""

    def setup_method(self) -> None:
        reset_runtime()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_tool_registered(self) -> None:
        """evals_evaluate_can_model tool must be registered."""
        tool = _get_tool("evals_evaluate_can_model")
        assert tool is not None

    def test_happy_path_without_y_score(self) -> None:
        """Without y_score, only accuracy/precision/recall/f1 are returned."""
        tool = _get_tool("evals_evaluate_can_model")
        result = tool.fn(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
        ).data.model_dump(exclude_none=True)
        assert result["accuracy"] == 1.0
        assert result["precision"] == 1.0
        assert result["recall"] == 1.0
        assert result["f1"] == 1.0
        assert "auroc" not in result
        assert "auprc" not in result
        assert "brier" not in result

    def test_happy_path_with_y_score(self) -> None:
        """With y_score and both classes present, auroc/auprc/brier appear."""
        tool = _get_tool("evals_evaluate_can_model")
        result = tool.fn(
            y_true=[0, 0, 1, 1],
            y_pred=[0, 0, 1, 1],
            y_score=[0.1, 0.2, 0.8, 0.9],
        ).data.model_dump(exclude_none=True)
        assert result["auroc"] == 1.0
        assert "auprc" in result
        assert "brier" in result
        assert 0.0 <= result["auprc"] <= 1.0
        assert 0.0 <= result["brier"] <= 1.0

    def test_evidence_tool_returns_canonical_identity_digest_and_metrics(self) -> None:
        y_true, y_pred, y_score = [0, 1], [0, 1], [0.2, 0.8]
        tool = _get_tool("evals_evaluate_can_model_evidence")
        result = tool.fn(y_true=y_true, y_pred=y_pred, y_score=y_score).data.model_dump()
        encoded = json.dumps(
            {"y_true": y_true, "y_pred": y_pred, "y_score": y_score},
            allow_nan=False, separators=(",", ":"), sort_keys=True,
        ).encode()
        assert result == {
            "schema": "evals.can-model-evidence", "version": "1.0",
            "evaluator_identity": "evals.can-model@v1",
            "input_digest": "sha256:" + hashlib.sha256(encoded).hexdigest(),
            "metrics": result["metrics"],
        }
        assert result["metrics"]["accuracy"] == 1.0
        assert result["metrics"]["auroc"] == 1.0
