"""Shared fixtures for protected Workflow-to-Agent execution tests."""
from __future__ import annotations

from types import SimpleNamespace

from factory.agent.mcp.managed_graph_tool import register
from factory.agent.runtime.execution_manifest import prepare_execution_manifest, store_manifest
from factory.agent.runtime.graph_contracts import GraphConfig
from factory.mcp_utils.interface import (
    ExecutionBinding, begin_service_invocation, end_service_invocation,
    mint_internal_invocation_claims, reset_internal_invocation_claims,
    set_internal_invocation_claims,
)
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

WORKFLOW_RUN_ID = "wfr:v1:run"
ATTEMPT_ID = "wfa:v1:attempt"
REVISION = 3
ENGINE_ID = "strands_graph"
REGISTRATION_DIGEST = "a" * 64
REQUEST_DIGEST = "b" * 64
OWNERSHIP_FIELDS = ("workflow_run_id", "attempt_id", "revision", "engine_id",
                    "registration_digest", "request_digest", "provider_request_digest")


class Assembled:
    def __init__(self, manifest, graph) -> None:
        self.manifest, self.graph, self.closed = manifest, graph, False

    def close(self) -> None:
        self.closed = True


def manifest():
    config = GraphConfig.model_validate({"id": "graph", "name": "Graph", "nodes": [{
        "id": "a", "type": "agent", "model": "model", "system_prompt": "hello",
        "tools": [], "skills": [],
    }], "entry_point": "a", "resumable": True})
    return prepare_execution_manifest(config, "work", {"domain": "planning"}, invocation_state={
        "workflow_run_id": WORKFLOW_RUN_ID, "attempt_id": ATTEMPT_ID,
        "revision": REVISION, "execution_mode": "managed", "durable": True,
    })


async def arguments(**changes) -> tuple[object, dict]:
    frozen = manifest()
    descriptor = await store_manifest(frozen)
    values = {"request": descriptor.model_dump(mode="json"),
        "provider_request_digest": frozen.digest.value, "workflow_run_id": WORKFLOW_RUN_ID,
        "attempt_id": ATTEMPT_ID, "revision": REVISION, "engine_id": ENGINE_ID,
        "registration_digest": REGISTRATION_DIGEST, "request_digest": REQUEST_DIGEST}
    values.update(changes)
    return frozen, values


def ownership(values: dict) -> dict:
    return {key: values[key] for key in OWNERSHIP_FIELDS}


def server() -> ToolCatalog:
    mcp = ToolCatalog("execution-test")
    register(mcp, SimpleNamespace(swarm_registry=None, agent_registry=None, graph_registry=None))
    return mcp


async def protected_call(mcp: ToolCatalog, name: str, values: dict):
    tool = await mcp.get_tool(name)
    binding = ExecutionBinding(**ownership(values))
    claims = mint_internal_invocation_claims(caller="workflow", audience="agent",
        target_tool=name, binding=binding, target=tool)
    token = set_internal_invocation_claims(claims)
    state = None
    try:
        state = begin_service_invocation(tool, audience="agent", target_tool=name,
                                         arguments=values)
        return await mcp.call_tool(name, values)
    finally:
        end_service_invocation(state)
        reset_internal_invocation_claims(token)
