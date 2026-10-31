"""Abstract ports for agent brick — runtime Protocol interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, AsyncIterator, Protocol

if TYPE_CHECKING:
    # The PERSONA contract (registry_contracts.AgentConfig), NOT the
    # framework-agnostic ``AgentConfig`` dataclass defined below. Aliased
    # to keep the two straight (bd:python-factory-d4roe.1).
    from .registry_contracts import AgentConfig as PersonaConfig


@dataclass
class AgentConfig:
    """Framework-agnostic agent configuration."""
    name: str
    system_prompt: str = ""
    model: str = ""
    tools: list[Any] = field(default_factory=list)
    callback_handler: Any = None
    trace_attributes: dict[str, str] = field(default_factory=dict)
    # Optional SDK features — adapters pass these through when set
    hooks: dict[str, Any] = field(default_factory=dict)
    session_manager: Any = None
    structured_output_model: Any = None
    conversation_manager: Any = None
    description: str = ""
    plugins: list[Any] = field(default_factory=list)
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Result from an agent invocation."""
    output: str
    status: str = "completed"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class NodeExecution:
    """Per-node execution detail from a swarm run."""
    node_id: str
    status: str = ""
    usage: dict[str, int] = field(default_factory=dict)
    metrics_summary: dict[str, Any] = field(default_factory=dict)
    result_text: str = ""


class AgentRuntime(Protocol):
    """Port: Create and run individual agents."""

    def create_agent(self, config: AgentConfig) -> Any:
        """Create an agent from configuration."""
        ...

    async def invoke_async(self, agent: Any, message: str, **kwargs: Any) -> AgentResult:
        """Invoke an agent asynchronously."""
        ...

    async def stream_async(self, agent: Any, message: str, **kwargs: Any) -> AsyncIterator[Any]:
        """Stream agent responses."""
        ...


class SwarmRuntime(Protocol):
    """Port: Create and run multi-agent swarms."""

    def create_swarm(
        self,
        agents: list[Any],
        entry_point: Any,
        max_handoffs: int = 20,
        max_iterations: int = 20,
        execution_timeout: float = 900.0,
        node_timeout: float = 300.0,
        repetitive_handoff_detection_window: int = 8,
        repetitive_handoff_min_unique_agents: int = 3,
        hooks: list[Any] | None = None,
    ) -> Any:
        """Create a swarm. ``hooks`` are SDK ``HookProvider`` instances."""
        ...

    async def invoke_async(
        self, swarm: Any, task: str, context: dict[str, Any] | None = None
    ) -> SwarmResult:
        """Execute a swarm asynchronously."""
        ...

    async def stream_async(
        self, swarm: Any, task: str, context: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream swarm execution events."""
        ...


class GraphRuntime(Protocol):
    """Port: Create and run agent graphs."""

    def create_builder(self) -> Any:
        """Create a graph builder."""
        ...
    def add_node(self, builder: Any, node: Any, node_id: str) -> None:
        """Add a node to the graph builder."""
        ...
    def add_edge(
        self, builder: Any, source: str, target: str, condition: Any | None = None
    ) -> None:
        """Add an edge to the graph builder."""
        ...
    def set_entry_point(self, builder: Any, node_id: str) -> None:
        """Set the entry point for the graph."""
        ...
    def set_hook_providers(self, builder: Any, hooks: list[Any]) -> None:
        """Attach SDK ``HookProvider`` instances to the builder. No-op ok."""
        ...
    def build(self, builder: Any) -> Any:
        """Build the graph from the builder."""
        ...

    async def invoke_async(
        self, graph: Any, task: str, context: dict[str, Any] | None = None
    ) -> GraphResult:
        """Execute a graph asynchronously."""
        ...

    async def stream_async(
        self, graph: Any, task: str, context: dict[str, Any] | None = None
    ) -> AsyncIterator[dict[str, Any]]:
        """Stream graph execution events."""
        ...


class ToolLoader(Protocol):
    """Port: Load tools for agents."""

    def load_builtin_tools(self) -> list[Any]:
        """Load built-in tools from the framework."""
        ...
    def load_tool(self, spec: str) -> Any | None:
        """Load a specific tool by specification."""
        ...


class RegistryStore(Protocol):
    """Port: persistence for USER-created agent personas
    (bd:python-factory-d4roe.1).

    Built-in personas stay in CODE (``AGENTS_TYPED``); this port owns
    only the DATA tier — agents authored at runtime. The disk adapter
    backs local dev; an AgentCore-backed adapter slots in later behind
    the same Protocol (tenet #2 polymorphic). Implementations return
    PERSONA ``AgentConfig`` (``registry_contracts.AgentConfig``), never
    the framework-agnostic ``ports.AgentConfig`` dataclass above.
    """

    def load_personas(self) -> list[PersonaConfig]:
        """Return all persisted user personas (validated)."""
        ...
    def save_persona(self, config: PersonaConfig) -> None:
        """Persist a single user persona (create or update)."""
        ...
    def delete_persona(self, agent_id: str) -> bool:
        """Remove a persisted persona. Return True if one was removed."""
        ...

# ChatAgentPort moved to chat_port.py to keep this file under 200 LOC
from .chat_port import ChatAgentPort  # noqa: E402, F401
# SwarmResult / GraphResult moved to multiagent_results.py for the same
# reason (bd-qev3 added run_id field for chat-tool-result correlation).
from .multiagent_results import SwarmResult, GraphResult  # noqa: E402, F401
