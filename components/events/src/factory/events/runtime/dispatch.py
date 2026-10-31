"""Event subscription dispatch — routes events to MCP handlers.

Public surface: ``dispatch_mcp_handler``. Argument-construction and
side-effect helpers live in :mod:`dispatch_args` to keep this file under
the 200 LOC budget.
"""
from __future__ import annotations

import logging
import threading

from .dispatch_args import _build_args, _persist_eval_result
from .models import Event
from .subscriptions import SubscriptionDefinition

logger = logging.getLogger(__name__)

__all__ = ["dispatch_mcp_handler"]


def dispatch_mcp_handler(
    sub: SubscriptionDefinition, event: Event,
) -> bool:
    """Dispatch to an MCP tool handler via background thread."""
    try:
        from factory.mcp_utils.interface import get_service
        invoker = get_service("tool_invoker")
        if not invoker:
            logger.warning("dispatch %s: no tool_invoker", sub.id)
            return False
        tool_name = sub.handler.removeprefix("mcp:")
        args = _build_args(tool_name, sub, event, invoker)

        def _run() -> None:
            try:
                # Rewards dispatch — dedicated handler
                if tool_name == "rewards_dispatch":
                    from .rewards_handler import handle_rewards_process
                    result = handle_rewards_process(event, invoker)
                elif tool_name == "chat_reward_dispatch":
                    from .chat_turn_handler import handle_chat_turn_reward
                    result = handle_chat_turn_reward(event, invoker)
                elif tool_name == "chat_feedback_dispatch":
                    from .chat_turn_handler import handle_chat_feedback
                    result = handle_chat_feedback(event, invoker)
                elif tool_name == "telemetry_reward_dispatch":
                    from .telemetry_handler import handle_telemetry_reward
                    result = handle_telemetry_reward(event, invoker)
                elif tool_name == "blockchain_reward_dispatch":
                    from .learning_handlers import handle_blockchain_reward
                    result = handle_blockchain_reward(event, invoker)
                elif tool_name == "memory_learning_dispatch":
                    from .learning_handlers import handle_memory_learning
                    result = handle_memory_learning(event, invoker)
                elif tool_name == "convergence_dispatch":
                    from .learning_handlers import handle_convergence_check
                    result = handle_convergence_check(event, invoker)
                elif tool_name == "workflow_improvement_dispatch":
                    from .learning_handlers import handle_workflow_improvement
                    result = handle_workflow_improvement(event, invoker)
                elif tool_name == "freshness_dispatch":
                    from .freshness_handler import handle_freshness_check
                    result = handle_freshness_check(event, invoker)
                elif tool_name == "generic_score_dispatch":
                    from .generic_score_dispatch import handle_generic_score_dispatch
                    result = handle_generic_score_dispatch(event, invoker)
                elif tool_name == "graph_project_event":
                    from .projection_dispatch import dispatch_projection
                    result = dispatch_projection(event)
                else:
                    result = invoker(tool_name, **args)
                logger.info("dispatch %s: %s OK", sub.id, tool_name)
                # Persist eval results to graph + emit event
                if tool_name in ("evals_evaluate_multi",
                                 "evals_evaluate_session"):
                    _persist_eval_result(
                        invoker, event.payload, result)
            except Exception as e:
                logger.warning("dispatch %s: %s failed: %s",
                               sub.id, tool_name, e)
        threading.Thread(
            target=_run, daemon=True,
            name=f"dispatch-{sub.id}",
        ).start()
        return True
    except Exception as e:
        logger.warning("dispatch %s failed: %s", sub.id, e)
        return False
