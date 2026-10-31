from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class LogSnapshot:
    """Log metrics snapshot."""
    total: int = 0
    by_severity: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total": self.total,
            "by_severity": dict(self.by_severity),
        }


@dataclass
class MetricsSnapshot:
    started_at: float = field(default_factory=time.time)
    llm_interactions: int = 0
    llm_input_tokens: int = 0
    llm_output_tokens: int = 0
    llm_cost_usd: float = 0.0
    agent_executions: int = 0
    tool_invocations: int = 0
    errors: int = 0
    last_latency_ms: float | None = None
    logs: LogSnapshot = field(default_factory=LogSnapshot)

    def to_dict(self) -> dict[str, Any]:
        return {
            "started_at": self.started_at,
            "llm": {
                "interactions": self.llm_interactions,
                "input_tokens": self.llm_input_tokens,
                "output_tokens": self.llm_output_tokens,
                "total_tokens": self.llm_input_tokens + self.llm_output_tokens,
                "cost_usd": round(self.llm_cost_usd, 6),
                "last_latency_ms": self.last_latency_ms,
            },
            "agent": {"executions": self.agent_executions},
            "tools": {"invocations": self.tool_invocations},
            "logs": self.logs.to_dict(),
            "errors": self.errors,
        }
