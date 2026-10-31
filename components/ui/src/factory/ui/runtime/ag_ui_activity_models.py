"""Pydantic contracts for sub-agent activity-message payloads (bd-6zyg).

Strict discriminated union — ``activityType`` selects sub-agent or
``terminal.command`` content. ``extra="forbid"``
mirrors the chat-stream models in ``factory.agent.runtime.models`` so SDK
shapes can't sneak through and the FE Zod schema matches exactly.

These models describe the ``content`` payload carried by AG-UI
``ACTIVITY_SNAPSHOT`` / ``ACTIVITY_DELTA`` events (see
``ag_ui_mapper_activity`` for the wire-shape pin). The discriminator
field is ``activityType`` and matches the strings used by the FE
renderers in
``frontends/next-dashboard/lib/copilotkit/subagent-activity-renderer.tsx``.

Verdicts: meta-architect ``16ce8a90`` (mapper-in-ui-brick + Pydantic
contract REQUIRED), strands-expert ``7184849b`` (event-shape pin).
"""
from __future__ import annotations

from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _StrictModel(BaseModel):
    """Base — forbids extra fields so SDK shapes can't sneak through."""

    model_config = ConfigDict(extra="forbid")


class NodeActivity(_StrictModel):
    """Per-node lifecycle row for a swarm or graph run."""

    node_id: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: float | None = None
    stopped_at: float | None = None
    handoff_from: str | None = None
    error: str | None = None


class SubagentSwarmActivity(_StrictModel):
    """Activity payload for ``agent_launch_swarm`` runs."""

    activityType: Literal["subagent.swarm"] = "subagent.swarm"
    run_id: str
    swarm_id: str
    status: Literal["running", "completed", "failed"]
    agent_count: int
    nodes: list[NodeActivity] = Field(default_factory=list)
    started_at: float
    completed_at: float | None = None
    error: str | None = None


class SubagentGraphActivity(_StrictModel):
    """Activity payload for ``agent_invoke_graph`` runs."""

    activityType: Literal["subagent.graph"] = "subagent.graph"
    run_id: str
    graph_id: str
    status: Literal["running", "completed", "failed"]
    nodes: list[NodeActivity] = Field(default_factory=list)
    started_at: float
    completed_at: float | None = None
    error: str | None = None


class TerminalCommandActivity(_StrictModel):
    activityType: Literal["terminal.command"] = "terminal.command"
    run_id: str
    status: Literal["running", "completed", "failed", "cancelled", "timed_out"]
    command: str = ""
    cwd: str = "."
    stdout: str = ""
    stderr: str = ""
    started_at: float
    completed_at: float | None = None
    exit_code: int | None = None
    duration_ms: int | None = None
    truncated: bool = False


SubagentActivity = Annotated[
    Union[SubagentSwarmActivity, SubagentGraphActivity, TerminalCommandActivity],
    Field(discriminator="activityType"),
]


__all__ = [
    "NodeActivity",
    "SubagentActivity",
    "SubagentGraphActivity",
    "SubagentSwarmActivity",
    "TerminalCommandActivity",
]
