"""
SuperAgent - Main orchestration class.

The SuperAgent manages registries, executors, and MCP server exposure.
It loads configuration from a directory and exposes tools via FastMCP.
"""

from pathlib import Path
from typing import Any, Callable
import yaml

from factory.agent.registry.agents import AgentRegistry
from factory.agent.registry.swarms import SwarmRegistry
from factory.agent.registry.graphs import GraphRegistry
from factory.agent.registry.squads import SquadRegistry
from factory.agent.registry.tools import ToolRegistry
from factory.agent.server import create_mcp_server


class SuperAgent:
    """
    Portable Super Agent with config-driven behavior.

    Usage:
        agent = SuperAgent(config_dir="./config")
        await agent.initialize()
        agent.mcp.run()  # Start MCP server (stdio)
    """

    def __init__(
        self,
        config_dir: str = "./config",
        extra_tools: list[tuple[str, Callable[..., Any]]] | None = None,
        extra_nodes: dict[str, type] | None = None,
    ):
        """
        Initialize SuperAgent.

        Args:
            config_dir: Path to configuration directory
            extra_tools: Additional tools to register [(name, func), ...]
            extra_nodes: Additional custom node types {name: class}
        """
        self.config_dir = Path(config_dir)
        self._extra_tools = extra_tools or []
        self._extra_nodes = extra_nodes or {}
        self._lifecycle_hooks: dict[str, list[Callable[..., Any]]] = {}
        self._initialized = False

        # Settings loaded during initialize
        self.settings: dict[str, Any] = {}

        # Registries (created during initialize)
        self.agent_registry: AgentRegistry | None = None
        self.swarm_registry: SwarmRegistry | None = None
        self.graph_registry: GraphRegistry | None = None
        self.squad_registry: SquadRegistry | None = None
        self.tool_registry: ToolRegistry | None = None

        # MCP server (created during initialize)
        self.mcp: Any = None

        # Active workflows for async execution
        self.workflows: dict[str, Any] = {}

        # Owner-scoped Crew store (M6.5) — lazily built by the Crew MCP
        # tools over ``config_dir/crews`` when first used.
        self.crew_store: Any = None
        # Owner-scoped approval list; production composes durable SQLite.
        self.approval_store: Any = None
        self.skill_policy_store: Any = None

    def register_tool(self, name: str, func: Callable[..., Any]) -> None:
        """Register a custom deterministic tool."""
        self._extra_tools.append((name, func))

    def register_custom_node(self, name: str, cls: type) -> None:
        """Register a custom graph node type."""
        self._extra_nodes[name] = cls

    def on(self, event: str, handler: Callable[..., Any]) -> None:
        """
        Register a lifecycle hook.

        Events:
            - swarm_start: Called when a swarm starts
            - swarm_complete: Called when a swarm completes
            - graph_start: Called when a graph starts
            - graph_complete: Called when a graph completes
            - tool_call: Called when a tool is invoked
            - error: Called on errors
        """
        if event not in self._lifecycle_hooks:
            self._lifecycle_hooks[event] = []
        self._lifecycle_hooks[event].append(handler)

    async def _emit(self, event: str, *args: Any, **kwargs: Any) -> None:
        """Emit a lifecycle event to all registered handlers."""
        for handler in self._lifecycle_hooks.get(event, []):
            result = handler(*args, **kwargs)
            if hasattr(result, "__await__"):
                await result

    async def initialize(self) -> None:
        """Load all registries and set up MCP server."""
        if self._initialized:
            return

        # Load settings
        self.settings = self._load_settings()

        # Initialize registries
        self.agent_registry = AgentRegistry(self.config_dir / "agents")
        self.swarm_registry = SwarmRegistry(self.config_dir / "swarms")
        self.graph_registry = GraphRegistry(self.config_dir / "graphs")
        self.squad_registry = SquadRegistry(self.config_dir / "squads")
        self.tool_registry = ToolRegistry(self.config_dir / "tools")

        # Load configs
        await self.agent_registry.load()
        await self.swarm_registry.load()
        await self.graph_registry.load()
        await self.squad_registry.load()
        await self.tool_registry.load()

        # Unify the persona read path (bd:python-factory-d4roe.1): wire
        # the registry's user-persona store as the process-wide store so
        # the free-function chat resolver (resolve_agent_config) sees the
        # same user-created personas this registry does. Built-ins are
        # already seeded in load(); the store only carries DATA-tier
        # (user-authored) personas.
        from factory.agent.registry.unified import set_default_store
        set_default_store(self.agent_registry.store)

        # Register extra tools
        for name, func in self._extra_tools:
            self.tool_registry.register(name, func)

        # Register extra nodes
        for name, cls in self._extra_nodes.items():
            self.graph_registry.register_node_type(name, cls)

        # Create MCP server with tools
        if self.approval_store is None:
            import os
            from .runtime.adapters.approval_policy_store import SqliteApprovalPolicyStore
            path = os.getenv(
                "COMPANION_X_APPROVAL_POLICY_DB_PATH",
                str(self.config_dir / "agent-approval.db"),
            )
            self.approval_store = SqliteApprovalPolicyStore(path)
            from .runtime.adapters.skill_policy_store import SqliteSkillPolicyStore
            self.skill_policy_store = SqliteSkillPolicyStore(path)
        self.mcp = create_mcp_server(self)

        self._initialized = True

    def _load_settings(self) -> dict[str, Any]:
        """Load settings from settings.yaml."""
        settings_path = self.config_dir / "settings.yaml"
        if settings_path.exists():
            with open(settings_path) as f:
                return yaml.safe_load(f) or {}
        return {}

    def get_capabilities(self) -> dict[str, Any]:
        """Get all available capabilities."""
        return {
            "deterministic_tools": self.tool_registry.list_tools() if self.tool_registry else [],
            "swarms": self.swarm_registry.list_swarms() if self.swarm_registry else [],
            "graphs": self.graph_registry.list_graphs() if self.graph_registry else [],
            "agents": self.agent_registry.list_agents() if self.agent_registry else [],
        }

    def health_check(self) -> dict[str, Any]:
        """Return health status."""
        return {
            "status": "healthy" if self._initialized else "not_initialized",
            "config_dir": str(self.config_dir),
            "agents_loaded": len(self.agent_registry.agents) if self.agent_registry else 0,
            "swarms_loaded": len(self.swarm_registry.swarms) if self.swarm_registry else 0,
            "graphs_loaded": len(self.graph_registry.graphs) if self.graph_registry else 0,
            "squads_loaded": len(self.squad_registry.squads) if self.squad_registry else 0,
        }
