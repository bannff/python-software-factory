"""Agent core - high-level convenience functions.

Provides simple API for common agent operations without needing
to manage the full SuperAgent lifecycle.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

# Lazy import to avoid circular dependencies
_agent: "SuperAgent | None" = None


def get_agent(config_dir: str = "./config") -> "SuperAgent":
    """Get or create the default SuperAgent instance.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        Initialized SuperAgent instance.
    """
    global _agent
    if _agent is None:
        from .agent import SuperAgent
        _agent = SuperAgent(config_dir=config_dir)
    return _agent


def reset_agent() -> None:
    """Reset the global agent instance (for testing)."""
    global _agent
    _agent = None


def list_agents(config_dir: str = "./config") -> list[str]:
    """List all registered agent configurations.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        List of agent names.
    """
    agent = get_agent(config_dir)
    if agent.agent_registry:
        return agent.agent_registry.list_agents()
    return []


def list_swarms(config_dir: str = "./config") -> list[str]:
    """List all registered swarm configurations.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        List of swarm names.
    """
    agent = get_agent(config_dir)
    if agent.swarm_registry:
        return agent.swarm_registry.list_swarms()
    return []


def list_graphs(config_dir: str = "./config") -> list[str]:
    """List all registered graph configurations.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        List of graph names.
    """
    agent = get_agent(config_dir)
    if agent.graph_registry:
        return agent.graph_registry.list_graphs()
    return []


def register_tool(name: str, func: Callable[..., Any]) -> None:
    """Register a custom tool with the default agent.
    
    Args:
        name: Tool name.
        func: Tool function.
    """
    agent = get_agent()
    agent.register_tool(name, func)


def get_capabilities(config_dir: str = "./config") -> dict[str, Any]:
    """Get all available capabilities from the agent.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        Dictionary of capabilities.
    """
    agent = get_agent(config_dir)
    return agent.get_capabilities()


def health_check(config_dir: str = "./config") -> dict[str, Any]:
    """Check agent health status.
    
    Args:
        config_dir: Path to configuration directory.
        
    Returns:
        Health status dictionary.
    """
    agent = get_agent(config_dir)
    return agent.health_check()
