"""Neutral ports for Agent invocation and append-only archival."""
from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ArchiveSinkPort(Protocol):
    def append(self, agent_id: str, record: dict[str, Any]) -> None:
        """Append a record without truncating prior history."""
        ...


@runtime_checkable
class AgentInvocationPort(Protocol):
    def invoke(
        self, *, agent_id: str, session_id: str, content: str,
        system_prompt: str | None = None,
    ) -> Any:
        """Invoke one normalized Agent turn; sync and async results are accepted."""
        ...
