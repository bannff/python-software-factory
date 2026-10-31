"""Strict Pydantic-v2 ingress and ToolResult egress for Worker."""
from __future__ import annotations

import asyncio
from inspect import signature
from typing import get_type_hints

import pytest
from factory.mcp_utils.interface import ToolResult
from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.worker.core import TaskInfo, WorkerHealth
from factory.worker.runtime.runtime import WorkerRuntime
from factory.worker.server import create_mcp_server

EXPECTED = {
    "worker_get_capabilities": "deterministic",
    "worker_health_check": "deterministic",
    "worker_describe_config_schema": "deterministic",
    "worker_list_tasks": "deterministic",
    "worker.send_task": "operational",
    "worker.execute_tool": "operational",
    "worker.list_mcp_tools": "operational",
    "worker.authoring.get_status": "authoring",
    "worker.authoring.switch_backend": "authoring",
    "worker.authoring.set_config": "authoring",
}


class StubRuntime(WorkerRuntime):
    def health_check(self):
        return WorkerHealth(healthy=True, backend="celery", queues=["default"])

    def list_tasks(self):
        return [TaskInfo(name="example", queue="default", state="PENDING")]

    def send_task(self, name, args=(), kwargs=None):
        return {"task_id": "task-1", "args": list(args), "kwargs": kwargs or {}}


def _tools():
    server = create_mcp_server(StubRuntime(), enable_authoring=True)
    return {tool.name: tool for tool in asyncio.run(server.list_tools())}


def test_exact_catalog_categories_and_typed_annotations() -> None:
    tools = _tools()
    assert set(tools) == set(EXPECTED)
    for name, category in EXPECTED.items():
        function = tools[name].fn
        assert function._mcp_category == category
        input_model = function._mcp_input_model
        output_model = function._mcp_output_model
        assert output_model.__module__.startswith("factory.worker.mcp.contracts")
        assert input_model.model_config["extra"] == "forbid"
        assert input_model.model_config["strict"] is True
        assert output_model.model_config["extra"] == "forbid"
        assert output_model.model_config["strict"] is True
        assert get_type_hints(function)["return"] == ToolResult[output_model]
        assert signature(function).return_annotation is not None


def test_flat_wire_inputs_are_strict() -> None:
    tools = _tools()
    with pytest.raises(SchemaMigrationError):
        tools["worker_get_capabilities"].fn(unexpected=True)
    with pytest.raises(SchemaMigrationError):
        tools["worker.authoring.switch_backend"].fn(backend="dagster", unexpected=True)
    with pytest.raises(SchemaMigrationError):
        tools["worker.send_task"].fn(name="task", args="not-a-list")


def test_schema_and_runtime_outputs_are_enveloped() -> None:
    tools = _tools()
    capabilities = tools["worker_get_capabilities"].fn()
    schema = tools["worker_describe_config_schema"].fn()
    tasks = tools["worker_list_tasks"].fn()
    assert all(isinstance(result, ToolResult) and result.ok for result in (capabilities, schema, tasks))
    assert capabilities.data.backends == ["celery", "dagster", "fargate_sqs"]
    assert schema.data.properties["backend"]["enum"] == ["celery", "dagster", "fargate_sqs"]
    assert tasks.data.tasks[0].name == "example"


def test_native_resources_and_prompts_remain_available() -> None:
    server = create_mcp_server(StubRuntime(), enable_authoring=True)
    resources = {str(item.uri) for item in asyncio.run(server.list_resources())}
    prompts = {item.name for item in asyncio.run(server.list_prompts())}
    assert resources == {"worker://health", "worker://backends", "worker://docs"}
    assert prompts == {"configure_worker", "debug_worker"}
    docs = asyncio.run(server.read_resource("worker://docs"))
    assert "fargate_sqs" in docs.contents[0].content
    prompt = asyncio.run(server.render_prompt("configure_worker"))
    assert "concurrency" in prompt.messages[0].content.text


def test_input_json_is_bounded() -> None:
    tools = _tools()
    with pytest.raises(SchemaMigrationError):
        tools["worker.send_task"].fn(name="task", args=list(range(1_025)))
