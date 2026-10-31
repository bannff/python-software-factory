"""Framework-neutral contracts for bounded Agent runtime adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from .models import FrontendToolSpec


@dataclass(frozen=True)
class RuntimeAdapterDescriptor:
    """Trusted identity and supported features of one runtime adapter."""

    adapter_id: str
    package_versions: tuple[tuple[str, str], ...]
    features: frozenset[str] = frozenset()


@dataclass(frozen=True)
class RuntimeInvocation:
    """One scope-bound, attempt-local Agent execution request."""

    invocation_id: str
    agent_id: str
    prompt: str
    capability_scope_digest: str
    model_id: str = ""
    memory_scope: str = "default"
    # Row 3 (feature-map): Persistent/Incognito/Temporary. Empty means the
    # caller made no explicit per-chat choice; the session-binding seam
    # resolves it to the session's actual materialized mode (never invents
    # an owner-preference default itself -- that resolution belongs to the
    # caller that first constructs the request, same as memory_scope).
    memory_mode: str = ""
    # M7.6 exit criterion #2 (feature-map): the closed registry name of a
    # structured-output schema this invocation's node should be resolved
    # against (e.g. "loop-cycle-report-v1", per
    # ``graph_output_models.resolve_output_schema``). Empty means an
    # ordinary free-text turn -- most invocations. Validated against the
    # REAL registry rather than a second hardcoded set, so the one list
    # in ``graph_output_models._SCHEMAS`` can never drift from what this
    # contract accepts.
    output_schema: str = ""
    thread_id: str | None = None
    # Row 16 (feature-map): the checkpoint id a prior regenerate/variant
    # switch pinned as "current" for this thread (materialized from
    # ``SessionRecord.active_checkpoint_id`` by the session-binding seam,
    # same as ``memory_mode``/``memory_scope`` above). ``None`` means no
    # branch has ever been created — the adapter falls through to
    # LangGraph's own latest-checkpoint resumption exactly as before this
    # field existed.
    checkpoint_id: str | None = None
    tenant_id: str | None = None
    owner_id: str | None = None
    metadata: Mapping[str, str] = field(default_factory=dict)
    messages: tuple[Mapping[str, Any], ...] = ()
    frontend_tools: tuple[FrontendToolSpec, ...] = ()

    def __post_init__(self) -> None:
        if self.model_id and (
            self.model_id != self.model_id.strip()
            or len(self.model_id) > 256
            or any(ord(char) < 32 for char in self.model_id)
        ):
            raise ValueError("model_id must be a bounded non-control string")
        if (
            not self.memory_scope
            or self.memory_scope != self.memory_scope.strip()
            or len(self.memory_scope) > 128
            or any(ord(char) < 32 for char in self.memory_scope)
        ):
            raise ValueError("memory_scope must be a bounded non-empty non-control string")
        if self.memory_mode and self.memory_mode not in {"persistent", "incognito", "temporary"}:
            raise ValueError("memory_mode must be persistent, incognito, temporary, or empty")
        if self.output_schema:
            from .graph_output_models import resolve_output_schema
            try:
                resolve_output_schema(self.output_schema)
            except ValueError as exc:
                raise ValueError("output_schema must be a known registry name or empty") from exc
        values = (self.tenant_id, self.owner_id)
        if (values[0] is None) != (values[1] is None) or any(
            value is not None and not value.strip() for value in values
        ):
            raise ValueError("tenant_id and owner_id must be nonempty and set together")


@dataclass(frozen=True)
class RuntimeLifecycleEvent:
    """A normalized ordered event emitted by a runtime adapter."""

    invocation_id: str
    sequence: int
    kind: str
    payload: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeResult:
    """Terminal result of a bounded Agent execution."""

    invocation_id: str
    output: str
    status: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GraphNode:
    """One declared bounded graph node identified by a registered persona."""

    node_id: str
    agent_id: str
    # M7.6 exit criterion #2 (feature-map): the manifest's own
    # ``output_schema.name`` (e.g. "loop-cycle-report-v1"), threaded
    # through so a node's structured response can actually be produced
    # and lifted into the engine result -- previously dropped silently at
    # ``managed_graph_tool._execute``, which built a bare
    # ``GraphNode(node.id, node.id)`` with no channel for it at all.
    output_schema: str | None = None


@dataclass(frozen=True)
class GraphEdge:
    """One directed transition between declared graph nodes."""

    source: str
    target: str


@dataclass(frozen=True)
class GraphRequest:
    """Provider-neutral, attempt-local graph with explicit hard bounds."""

    invocation: RuntimeInvocation
    nodes: tuple[GraphNode, ...]
    edges: tuple[GraphEdge, ...]
    max_steps: int = 64
    timeout_seconds: float = 300.0

    def __post_init__(self) -> None:
        if self.max_steps < 1:
            raise ValueError("max_steps must be positive")
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")


__all__ = [
    "GraphEdge",
    "GraphNode",
    "GraphRequest",
    "RuntimeAdapterDescriptor",
    "RuntimeInvocation",
    "RuntimeLifecycleEvent",
    "RuntimeResult",
]
