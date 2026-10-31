"""Graph sink — materialises ToolInvocation entities and Session lineage.

Drain thread calls the graph brick DIRECTLY (bypassing aggregator +
instrumentation) to avoid GIL amplification — intentional exception
to the MCP-first tenet for telemetry infra. Resolves the graph
runtime via ``factory.mcp_server.get_brick_tool_map`` (public API).

Writer helpers live in ``_graph_sink_writers.py`` to keep this file
under the 200 LOC budget. Public API (``materialize``,
``set_workflow_run_id``, ``set_aggregator``) plus patched module-level
state remain here so existing test patches keep applying.
"""
from __future__ import annotations

import logging
import os
import threading
import time
from queue import SimpleQueue, Empty
from typing import Any
from uuid import uuid4

from . import _graph_sink_lineage as _lineage
from . import _graph_sink_writers as _w

logger = logging.getLogger(__name__)

_graph_runtime: Any | None = None
_invocation_counter: dict[str, int] = {}
_last_invocation_by_session: dict[str, str] = {}
_run_invocation_counter: dict[str, int] = {}
_last_invocation_by_run: dict[str, str] = {}
_current_workflow_run_id: str | None = None  # Set by executors

_SINK_QUEUE: SimpleQueue = SimpleQueue()
_SINK_THREAD: threading.Thread | None = None
_BATCH_SIZE, _BATCH_PAUSE = 50, 0.05  # batch size; seconds between batches


def _drain_loop() -> None:
    """Background thread that drains the sink queue in batches."""
    while True:
        batch = [_SINK_QUEUE.get()]
        if batch[0] is None:
            break
        for _ in range(_BATCH_SIZE - 1):
            try:
                fn = _SINK_QUEUE.get_nowait()
                if fn is None:
                    break
                batch.append(fn)
            except Empty:
                break
        for fn in batch:
            try:
                fn()
            except Exception:
                logger.debug("graph_sink drain failed", exc_info=True)
        time.sleep(_BATCH_PAUSE)


def _ensure_drain_thread() -> None:
    """Start the drain thread if not already running."""
    global _SINK_THREAD
    if _SINK_THREAD is None or not _SINK_THREAD.is_alive():
        _SINK_THREAD = threading.Thread(target=_drain_loop, daemon=True, name="graph-sink")
        _SINK_THREAD.start()


def set_aggregator(agg: Any) -> None:
    """Bind the Graph sink to the neutral catalog owned by ``agg``.

    Startup passes the process aggregator before publishing the server
    singleton. Resolving through that same object avoids re-entering server
    construction while preserving one catalog and one MCP surface.
    """
    global _graph_runtime
    try:
        _graph_runtime = agg.get_brick_tool_map("graph")
        if _graph_runtime:
            logger.info("graph_sink: direct graph brick access ready")
    except Exception as exc:
        logger.debug("graph_sink: direct access failed: %s", exc)
        _graph_runtime = None


def _is_enabled() -> bool:
    return os.environ.get("TELEMETRY_GRAPH_SINK", "false").lower() in ("1", "true", "yes")


def _is_recursive(brick_name: str, tool_name: str) -> bool:
    """Anti-recursion guard — skip graph-sink-on-graph calls."""
    if brick_name != "graph":
        return False
    return tool_name.startswith("graph_add") or tool_name.startswith("graph_query")


def _call_graph(tool_name: str, **kwargs: Any) -> Any:
    """Call graph directly, excluding the parent task's replay identity."""
    try:
        from ._graph_sink_call import call_graph
        return call_graph(_graph_runtime, tool_name, **kwargs)
    except Exception:
        logger.debug("graph_sink._call_graph failed", exc_info=True)
        return None


def set_workflow_run_id(run_id: str | None) -> None:
    """Set the current workflow run ID (thread-safe fallback)."""
    global _current_workflow_run_id
    _current_workflow_run_id = run_id


def get_workflow_run_id() -> str | None:
    """Read module-global workflow run ID — cross-thread fallback for instrumentation."""
    return _current_workflow_run_id


def _read_envelope() -> tuple[str | None, str | None, str | None, str | None]:
    try:
        from factory.mcp_utils.interface import get_envelope
        env = get_envelope() or {}
        wf_id = env.get("workflow_run_id") or env.get("run_id") or _current_workflow_run_id
        return env.get("session_id"), env.get("principal_id"), env.get("agent_id"), wf_id
    except Exception:
        return None, None, None, _current_workflow_run_id


def _proxy_call_graph(tool_name: str, **kwargs: Any) -> Any:
    """Indirection so writer helpers honour ``patch.object(graph_sink, '_call_graph')``.

    Writer helpers receive this proxy as their ``call_graph`` arg; the proxy
    re-resolves ``_call_graph`` from this module on every call so test patches
    rebind correctly.
    """
    return _call_graph(tool_name, **kwargs)


def materialize(
    brick_name: str, tool_name: str, success: bool,
    latency_ms: float, error: str | None = None,
    args_summary: dict | None = None, caller: str | None = None,
    result_summary: dict | None = None,
) -> None:
    """Enqueue a ToolInvocation write — never blocks the caller."""
    try:
        if not _is_enabled() or _is_recursive(brick_name, tool_name):
            return
        if not _graph_runtime:
            return

        session_id, principal_id, agent_id, workflow_run_id = _read_envelope()
        entity_id = f"tool-inv-{uuid4().hex[:12]}"
        safe_error = error[:200] if error else None

        # Derive invocation_type from context
        if workflow_run_id:
            invocation_type = "workflow"
        elif principal_id:
            invocation_type = "user"
        else:
            invocation_type = "system"

        # Compute run-scoped sequence (per workflow_run_id) — process-local
        # counter, no graph read-before-write. Used by NEXT_IN_RUN edges and
        # stored as a property on ToolInvocation for cheap ORDER BY queries.
        sequence: int | None = None
        if workflow_run_id:
            sequence = _run_invocation_counter.get(workflow_run_id, 0)
            _run_invocation_counter[workflow_run_id] = sequence + 1

        def _do_write() -> None:
            props = _lineage.build_invocation_props(
                entity_id, brick_name, tool_name, success, latency_ms,
                safe_error, session_id, principal_id, workflow_run_id,
                invocation_type, args_summary, caller, result_summary,
                sequence=sequence,
            )
            _lineage.write_invocation_with_lineage(
                _proxy_call_graph, entity_id, props, brick_name,
                session_id, principal_id, agent_id, workflow_run_id,
                _invocation_counter, _last_invocation_by_session,
                run_invocation_counter=_run_invocation_counter,
                last_by_run=_last_invocation_by_run,
            )

        _ensure_drain_thread()
        _SINK_QUEUE.put(_do_write)
    except Exception:
        logger.debug("graph_sink.materialize failed", exc_info=True)
