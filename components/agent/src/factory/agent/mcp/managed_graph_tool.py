"""Workflow-owned durable handoff to bounded LangGraph execution."""
from __future__ import annotations

import asyncio
from typing import Any, TYPE_CHECKING

from factory.mcp_utils.interface import ToolResult, ok, operational, service_only

from .contracts.execution import (
    CancelLangGraphAttemptInput, CancelLangGraphAttemptOutput,
    ExecuteLangGraphAttemptInput, ExecuteLangGraphAttemptOutput,
)
from ..runtime.execution_manifest.artifact_models import DefinitionDescriptor
from ..runtime.execution_manifest.artifacts import resolve_manifest
from ..runtime.managed_cancellation import ManagedCancellationRegistry
from ..runtime.managed_context import ManagedRunContext, managed_run_scope
from ..runtime.managed_handoff import ManagedServiceCapability
from ..runtime.runtime_contracts import GraphEdge, GraphNode, GraphRequest, RuntimeInvocation

if TYPE_CHECKING:
    from ..agent import SuperAgent

_ENGINE = "langgraph"


def register(
    mcp: Any, agent: SuperAgent | None = None,
    registry: ManagedCancellationRegistry | None = None,
) -> None:
    """Register private provider calls; Workflow remains the durable owner."""
    del agent
    cancellations = registry or ManagedCancellationRegistry()

    @mcp.tool()
    @service_only(callers={"workflow"}, binding="execution")
    @operational(
        input_model=CancelLangGraphAttemptInput,
        output_model=CancelLangGraphAttemptOutput,
    )
    def cancel_langgraph_attempt(
        workflow_run_id: str, attempt_id: str, revision: int, engine_id: str,
        registration_digest: str, request_digest: str, provider_request_digest: str,
    ) -> ToolResult[CancelLangGraphAttemptOutput]:
        _require_engine(engine_id)
        outcome = cancellations.cancel(
            workflow_run_id=workflow_run_id, attempt_id=attempt_id,
            revision=revision, manifest_digest=provider_request_digest,
        )
        return ok(CancelLangGraphAttemptOutput(
            workflow_run_id=workflow_run_id, attempt_id=attempt_id,
            revision=revision, engine_id=engine_id,
            registration_digest=registration_digest, request_digest=request_digest,
            provider_request_digest=provider_request_digest,
            manifest_digest=provider_request_digest, outcome=outcome,
        ))

    @mcp.tool()
    @service_only(callers={"workflow"}, binding="execution")
    @operational(
        input_model=ExecuteLangGraphAttemptInput,
        output_model=ExecuteLangGraphAttemptOutput,
    )
    async def execute_langgraph_attempt(
        request: dict, provider_request_digest: str, workflow_run_id: str,
        attempt_id: str, revision: int, engine_id: str,
        registration_digest: str, request_digest: str,
    ) -> ToolResult[ExecuteLangGraphAttemptOutput]:
        _require_engine(engine_id)
        current = asyncio.current_task()
        if current is None:
            raise RuntimeError("execution attempt requires an asyncio task owner")
        key = (workflow_run_id, attempt_id, revision, provider_request_digest)
        cancellations.register(
            workflow_run_id=workflow_run_id, attempt_id=attempt_id,
            revision=revision, manifest_digest=provider_request_digest,
            loop=asyncio.get_running_loop(), task=current,
        )
        try:
            capability = ManagedServiceCapability(
                workflow_run_id=workflow_run_id, attempt_id=attempt_id,
                revision=revision, engine_id=engine_id,
                registration_digest=registration_digest,
                request_digest=request_digest,
                provider_request_digest=provider_request_digest,
            )
            descriptor = DefinitionDescriptor.model_validate(request)
            dataset = capability.dataset_port() if descriptor.reference is not None else None
            manifest = await resolve_manifest(descriptor, dataset)
            if manifest.digest is None or manifest.digest.value != provider_request_digest:
                raise ValueError("attempt manifest_digest does not bind resolved manifest")
            managed = ManagedRunContext(
                run_id=workflow_run_id, attempt_id=attempt_id,
                attempt_revision=revision, execution_mode="managed",
                graph_id=manifest.graph_id,
                graph_definition_digest=provider_request_digest,
                input_manifest_digest=provider_request_digest,
            )
            with managed_run_scope(managed):
                result = await _execute(manifest, workflow_run_id)
            return ok(_output(
                workflow_run_id, attempt_id, revision, registration_digest,
                request_digest, provider_request_digest,
                status="completed" if result.status == "completed" else "failed",
                result={
                    "status": result.status, "output": result.output,
                    **dict(result.metadata),
                },
                error=None if result.status == "completed" else result.status,
                retryable=result.status not in {"completed", "cancelled"},
            ))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            return ok(_output(
                workflow_run_id, attempt_id, revision, registration_digest,
                request_digest, provider_request_digest, status="failed",
                result={}, error=f"{type(exc).__name__}: {exc}", retryable=False,
            ))
        finally:
            cancellations.unregister(key=key, task=current)


def _require_engine(engine_id: str) -> None:
    if engine_id != _ENGINE:
        raise ValueError("unsupported execution engine")


async def _execute(manifest: Any, workflow_run_id: str):
    from dataclasses import replace
    from factory.mcp_utils.interface import get_envelope
    from ..runtime.adapters import create_runtime_pair
    from ..runtime.managed_steering import managed_steering

    agents, graph = create_runtime_pair()
    context = manifest.invocation.context
    identity = get_envelope() or {}
    background_thread = context.get("background_thread_id")
    base = RuntimeInvocation(
        invocation_id=workflow_run_id, agent_id=manifest.graph_id,
        prompt=str(manifest.invocation.task),
        capability_scope_digest=agents.capability_scope_digest,
        model_id=str(context.get("model_id") or ""),
        memory_scope=str(context.get("memory_scope") or "default"),
        thread_id=str(background_thread) if background_thread else None,
        tenant_id=identity.get("tenant_id"), owner_id=identity.get("principal_id"),
        metadata={
            "execution_mode": "managed",
            "background_subagent": "true" if background_thread else "false",
        },
    )
    nodes = tuple(
        GraphNode(node.id, node.id, output_schema=(
            node.output_schema.name if node.output_schema is not None else None
        ))
        for node in manifest.nodes
    )
    edges = tuple(GraphEdge(edge.source, edge.target) for edge in manifest.edges)
    request = GraphRequest(
        invocation=base, nodes=nodes, edges=edges,
        max_steps=manifest.limits.max_node_executions,
        timeout_seconds=manifest.limits.execution_timeout,
    )
    registered = bool(background_thread and len(nodes) == 1)
    if registered:
        managed_steering.register(
            workflow_run_id, agents,
            replace(base, invocation_id=f"{workflow_run_id}:{nodes[0].node_id}",
                    agent_id=nodes[0].agent_id),
        )
    try:
        return await graph.invoke_graph(request)
    finally:
        if registered:
            managed_steering.unregister(workflow_run_id, agents)
        await graph.close()


def _output(
    run_id: str, attempt_id: str, revision: int, registration_digest: str,
    request_digest: str, manifest_digest: str, *, status: str,
    result: dict[str, Any], error: str | None, retryable: bool,
) -> ExecuteLangGraphAttemptOutput:
    return ExecuteLangGraphAttemptOutput(
        workflow_run_id=run_id, attempt_id=attempt_id, revision=revision,
        engine_id=_ENGINE, registration_digest=registration_digest,
        request_digest=request_digest, provider_request_digest=manifest_digest,
        manifest_digest=manifest_digest, execution_mode="managed", status=status,
        result=result, error=error, retryable=retryable,
    )
