"""Queued-guidance hook for the Strands chat adapter (steer port).

``BeforeModelCallEvent`` has NO ``add_input`` (only
``invocation_state``/tokens/``cancel`` — strands 1.56), so guidance is
injected by PREPENDING one synthetic ``user`` message to
``agent.messages`` in the hook callback. One-shot: the queue entry is
consumed when the next model boundary fires, mirroring
``langchain_steering.LangChainSteeringMiddleware.abefore_model``
(inject before the model, settle after it returns).

The injected message stays in the durable transcript (same permanence
as the LangChain middleware's ``{"messages": [...]}`` state update).
"""
from __future__ import annotations

from typing import Any

from strands.hooks import BeforeModelCallEvent, HookProvider, HookRegistry

_STEER_PREFIX = "[steer]"


class StrandsSteerHook(HookProvider):
    """Prepend queued guidance to ``agent.messages`` once per delivery."""

    def __init__(self) -> None:
        self._queued: dict[str, list[str]] = {}

    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        registry.add_callback(BeforeModelCallEvent, self._before_model_call)

    def queue(self, agent_name: str, content: str) -> None:
        """Stage guidance for the thread's next model boundary."""
        self._queued.setdefault(agent_name, []).append(content)

    def _before_model_call(self, event: BeforeModelCallEvent) -> None:
        pending = self._queued.pop(event.agent.name, None)
        if not pending:
            return
        blocks = [{"text": f"{_STEER_PREFIX} {content}"} for content in pending]
        event.agent.messages.insert(0, {"role": "user", "content": blocks})


__all__ = ["StrandsSteerHook"]
