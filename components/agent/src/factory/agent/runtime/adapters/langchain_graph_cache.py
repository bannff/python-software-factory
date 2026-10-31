"""Compiled-graph cache keyed on persona/model/tools/policy/output_schema.

Split out of ``langchain_runtime.py`` to keep that file under the 200 LOC
ceiling once the M7.6 ``output_schema``/``response_format`` wiring (row 3's
``memory_mode`` cache-key precedent, extended) pushed it over.
"""
from __future__ import annotations

import asyncio
from typing import Any

from ..approval_policy import ApprovalPolicyStore
from ..personas import resolve_agent_config
from ..steering_documents import apply_steering
from ..runtime_contracts import RuntimeInvocation
from .capability_policy import effective_persona_scope


class CompiledGraphCache:
    """Owns the ``{cache_key: compiled_graph}`` map and its build lock."""

    def __init__(
        self, capabilities: Any, approval_store: ApprovalPolicyStore,
        recall_middleware: tuple[Any, ...], steering: Any,
        local_tools: list[Any],
    ) -> None:
        self._capabilities = capabilities
        self._approval_store = approval_store
        self._recall_middleware = recall_middleware
        self._steering = steering
        self._local_tools = local_tools
        self._graphs: dict[tuple[Any, ...], Any] = {}
        self._lock = asyncio.Lock()

    async def get(
        self, request: RuntimeInvocation, checkpointer: Any, models: Any,
    ) -> Any:
        persona = resolve_agent_config(request.agent_id)
        effective = effective_persona_scope(self._capabilities.scope, persona)
        model_id = models.effective_id(request.model_id, persona.model)
        system_prompt, steering_digest = apply_steering(persona.system_prompt)
        # Dormant-runtime laziness: the langchain SDK imports below must stay
        # inside this build path (langgraph-legacy dependency-group).
        from .langchain_frontend_tools import build_frontend_tools, frontend_digest
        from .langchain_steering import SteeringContext
        from .langchain_tools import build_langchain_tools
        cache_key = (
            request.agent_id, model_id, frontend_digest(request.frontend_tools),
            effective.policy_id, effective.digest, steering_digest,
            request.output_schema,
        )
        if cache_key in self._graphs:
            return self._graphs[cache_key]
        async with self._lock:
            if cache_key not in self._graphs:
                from langchain.agents import create_agent
                from ..graph_output_models import resolve_output_schema
                tools = await build_langchain_tools(
                    self._capabilities, effective, self._approval_store)
                tools.extend(build_frontend_tools(request.frontend_tools))
                tools.extend(self._local_tools)
                self._graphs[cache_key] = create_agent(
                    models.get(model_id),
                    tools,
                    system_prompt=system_prompt,
                    middleware=(*self._recall_middleware, self._steering.middleware),
                    response_format=resolve_output_schema(request.output_schema or None),
                    context_schema=SteeringContext,
                    checkpointer=checkpointer,
                    name=request.agent_id,
                )
        return self._graphs[cache_key]

    def drop_model(self, model_id: str) -> None:
        self._graphs = {key: graph for key, graph in self._graphs.items()
                        if key[1] != model_id}

    def clear(self) -> None:
        self._graphs.clear()


__all__ = ["CompiledGraphCache"]
