"""Integration tests for typed Blueprint IaC MCP tools."""
from __future__ import annotations

import asyncio

from factory.blueprint.server import get_mcp_server


def _get_tool(name: str):
    return asyncio.run(get_mcp_server().get_tool(name))


class TestListSupportedServices:
    def test_returns_services_dict(self):
        result = _get_tool("blueprint_list_supported_services").fn()
        assert result.ok is True
        assert "dynamodb" in result.data.services
        assert result.data.services["dynamodb"].module


class TestValidateSpecs:
    def test_valid_spec(self):
        specs = [{"brick": "cache", "spec": {
            "service": "dynamodb", "construct": "Table", "props": {}}}]
        result = _get_tool("blueprint_validate_specs").fn(specs=specs)
        assert result.ok is True
        assert result.data.valid is True
        assert result.data.resource_count == 1

    def test_invalid_service_is_typed_negative(self):
        specs = [{"brick": "x", "spec": {
            "service": "unknown-svc", "construct": "X", "props": {}}}]
        result = _get_tool("blueprint_validate_specs").fn(specs=specs)
        assert result.ok is True
        assert result.data.valid is False
        assert result.data.errors

    def test_vpc_detection(self):
        specs = [{"brick": "graph", "spec": {
            "service": "neptune", "construct": "DatabaseCluster", "props": {}}}]
        result = _get_tool("blueprint_validate_specs").fn(specs=specs)
        assert result.data.vpc_required is True


class TestGenerateCdk:
    def test_generates_json_safe_files_and_metadata(self):
        specs = [{"brick": "cache", "spec": {
            "service": "dynamodb", "construct": "Table", "props": {}}}]
        result = _get_tool("blueprint_generate_cdk").fn(specs=specs, project_name="test-proj")
        assert result.ok is True
        assert "cdk/app.py" in result.data.files
        assert result.data.metadata["stacks"]

    def test_empty_specs_no_error(self):
        result = _get_tool("blueprint_generate_cdk").fn(specs=[], project_name="empty")
        assert result.ok is True
        assert result.data.project == "empty"


class TestGeneratePipeline:
    def test_generates_workflow(self):
        result = _get_tool("blueprint_generate_pipeline").fn(project_name="proj")
        assert result.ok is True
        assert ".github/workflows/deploy-infra.yml" in result.data.files
        assert result.data.renderer == "github_actions"

    def test_custom_stages(self):
        result = _get_tool("blueprint_generate_pipeline").fn(stages=["test", "deploy-dev"])
        assert result.ok is True
        assert result.data.metadata["stages"] == ["test", "deploy-dev"]

    def test_unknown_renderer_is_failure(self):
        result = _get_tool("blueprint_generate_pipeline").fn(renderer="jenkins")
        assert result.ok is False
        assert result.error
