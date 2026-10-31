"""Framework-neutral Agent invocation wiring for Worker runners."""
from __future__ import annotations

import inspect
from typing import Any, Callable

from .archive_ports import AgentInvocationPort, ArchiveSinkPort


def build_agent_invoke_fn(
    agent_id: str,
    *,
    runtime: AgentInvocationPort,
    archive_sink: ArchiveSinkPort,
    system_prompt: str | None = None,
) -> Callable[[str, str], Any]:
    """Adapt a normalized Agent invocation port to the runner callback contract."""

    async def invoke_fn(session_id: str, content: str) -> Any:
        archive_sink.append(agent_id, _record("user", content))
        result = runtime.invoke(
            agent_id=agent_id,
            session_id=session_id,
            content=content,
            system_prompt=system_prompt,
        )
        if inspect.isawaitable(result):
            result = await result
        archive_sink.append(agent_id, _record("assistant", _output(result)))
        return result

    return invoke_fn


def _output(result: Any) -> Any:
    if hasattr(result, "output"):
        return result.output
    if isinstance(result, dict) and "output" in result:
        return result["output"]
    return result


def _record(role: str, content: Any) -> dict[str, Any]:
    from datetime import datetime, timezone

    return {
        "role": role,
        "content": content,
        "archived_at": datetime.now(timezone.utc).isoformat(),
    }
