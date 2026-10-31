"""Tests for sync brick primitives (get_resources, get_prompts)."""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.mcp_server.runtime.primitives import get_prompts, get_resources


def _mock_resource(uri="config://test", name="test_res", description="A resource"):
    r = MagicMock()
    r.uri, r.name, r.description = uri, name, description
    return r


def _mock_template(uri_template="config://test/{id}", name="test_tmpl",
                   description="A template"):
    t = MagicMock()
    t.uri_template, t.name, t.description = uri_template, name, description
    return t


def _mock_prompt_arg(name="query", description="Search query", required=True):
    a = MagicMock()
    a.name, a.description, a.required = name, description, required
    return a


def _mock_prompt(name="search_prompt", description="Search", arguments=None):
    p = MagicMock()
    p.name, p.description, p.arguments = name, description, arguments
    return p


class TestGetResources:
    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_returns_static_resources(self, mock_run_sync):
        res = _mock_resource("config://aws/identity", "aws_id", "AWS identity")
        mock_run_sync.side_effect = [[res], []]
        result = get_resources(MagicMock(), "config")
        assert result["brick"] == "config"
        assert result["count"] == 1
        assert result["resources"][0]["uri"] == "config://aws/identity"
        assert result["resources"][0]["type"] == "static"

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_returns_resource_templates(self, mock_run_sync):
        tmpl = _mock_template("config://aws/{service}", "aws_svc", "AWS service")
        mock_run_sync.side_effect = [[], [tmpl]]
        result = get_resources(MagicMock(), "config")
        assert result["count"] == 1
        assert result["resources"][0]["uri_template"] == "config://aws/{service}"
        assert result["resources"][0]["type"] == "template"

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_mixed_resources_and_templates(self, mock_run_sync):
        mock_run_sync.side_effect = [[_mock_resource()], [_mock_template()]]
        result = get_resources(MagicMock(), "mixed")
        assert result["count"] == 2
        types = [r["type"] for r in result["resources"]]
        assert "static" in types and "template" in types

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_empty_resources(self, mock_run_sync):
        mock_run_sync.side_effect = [[], []]
        result = get_resources(MagicMock(), "empty_brick")
        assert result["count"] == 0 and result["resources"] == []

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_none_from_list_calls(self, mock_run_sync):
        mock_run_sync.side_effect = [None, None]
        result = get_resources(MagicMock(), "none_brick")
        assert result["count"] == 0

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_description_defaults_to_empty_string(self, mock_run_sync):
        res = _mock_resource()
        res.description = None
        mock_run_sync.side_effect = [[res], []]
        result = get_resources(MagicMock(), "brick")
        assert result["resources"][0]["description"] == ""


class TestGetPrompts:
    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_returns_prompts_with_arguments(self, mock_run_sync):
        arg = _mock_prompt_arg("query", "Search query", True)
        prompt = _mock_prompt("search", "Search docs", [arg])
        mock_run_sync.return_value = [prompt]
        result = get_prompts(MagicMock(), "kb")
        assert result["count"] == 1
        assert result["prompts"][0]["name"] == "search"
        assert result["prompts"][0]["arguments"][0]["required"] is True

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_prompt_with_no_arguments(self, mock_run_sync):
        mock_run_sync.return_value = [_mock_prompt("simple", "Simple", None)]
        result = get_prompts(MagicMock(), "brick")
        assert result["prompts"][0]["arguments"] == []

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_empty_prompts(self, mock_run_sync):
        mock_run_sync.return_value = []
        result = get_prompts(MagicMock(), "empty")
        assert result["count"] == 0

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_none_from_list_prompts(self, mock_run_sync):
        mock_run_sync.return_value = None
        result = get_prompts(MagicMock(), "none_brick")
        assert result["count"] == 0

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_argument_without_required_attr(self, mock_run_sync):
        arg = MagicMock(spec=[])
        arg.name, arg.description = "loose", "no required attr"
        mock_run_sync.return_value = [_mock_prompt("p", "desc", [arg])]
        result = get_prompts(MagicMock(), "brick")
        assert result["prompts"][0]["arguments"][0]["required"] is False

    @patch("factory.mcp_server.runtime.primitives._run_sync")
    def test_multiple_prompts(self, mock_run_sync):
        mock_run_sync.return_value = [
            _mock_prompt("first", "First", []),
            _mock_prompt("second", "Second", [_mock_prompt_arg()]),
        ]
        result = get_prompts(MagicMock(), "multi")
        assert result["count"] == 2
