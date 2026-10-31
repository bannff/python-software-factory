"""MCP resources for agent module."""

from __future__ import annotations

from typing import TYPE_CHECKING

from typing import Any

from .docs import get_doc, list_docs
from .templates import get_template, list_templates

if TYPE_CHECKING:
    from ..agent import SuperAgent


def register(mcp: Any, agent: "SuperAgent") -> None:
    """Register agent resources."""

    @mcp.resource("agent://docs")
    def agent_docs_list() -> str:
        """List available agent documentation."""
        docs = list_docs()
        lines = ["# Agent Documentation", ""]
        for doc in docs:
            lines.append(f"- agent://docs/{doc}")
        return "\n".join(lines)

    @mcp.resource("agent://docs/{name}")
    def agent_doc(name: str) -> str:
        """Get specific agent documentation.

        Includes 'event-protocol' for live UI integration.
        """
        doc = get_doc(name)
        if doc is None:
            return f"Documentation '{name}' not found. Available: {list_docs()}"
        return doc

    @mcp.resource("agent://templates")
    def agent_templates_list() -> str:
        """List available prompt templates."""
        templates = list_templates()
        lines = ["# Agent Templates", ""]
        for t in templates:
            lines.append(f"- agent://templates/{t}")
        return "\n".join(lines)

    @mcp.resource("agent://templates/{name}")
    def agent_template(name: str) -> str:
        """Get specific prompt template."""
        template = get_template(name)
        if template is None:
            return f"Template '{name}' not found. Available: {list_templates()}"
        return template

    @mcp.resource("agent://agents")
    def agent_registry_list() -> str:
        """Get registered agents."""
        if not agent.agent_registry:
            return "# Agents\n\nNo agent registry configured."
        
        agents = agent.agent_registry.list_agents()
        lines = ["# Registered Agents", ""]
        
        if not agents:
            lines.append("No agents registered.")
            return "\n".join(lines)
        
        for a in agents:
            lines.append(f"- {a['id']}: {a['name']}")
            if a.get('description'):
                lines.append(f"  {a['description']}")
        
        return "\n".join(lines)

    @mcp.resource("agent://swarms")
    def swarm_registry_list() -> str:
        """Get registered swarms."""
        if not agent.swarm_registry:
            return "# Swarms\n\nNo swarm registry configured."
        
        swarms = agent.swarm_registry.list_swarms_with_schemas()
        lines = ["# Registered Swarms", ""]
        
        if not swarms:
            lines.append("No swarms registered.")
            return "\n".join(lines)
        
        for s in swarms:
            lines.append(f"- {s.get('id', 'unknown')}: {s.get('name', 'Unnamed')}")
        
        return "\n".join(lines)

    @mcp.resource("agent://graphs")
    def graph_registry_list() -> str:
        """Get registered graphs."""
        if not agent.graph_registry:
            return "# Graphs\n\nNo graph registry configured."
        
        graphs = agent.graph_registry.list_graphs_with_schemas()
        lines = ["# Registered Graphs", ""]
        
        if not graphs:
            lines.append("No graphs registered.")
            return "\n".join(lines)
        
        for g in graphs:
            lines.append(f"- {g.get('id', 'unknown')}: {g.get('name', 'Unnamed')}")
        
        return "\n".join(lines)

    @mcp.resource("agent://workflows")
    def workflows_list() -> str:
        """Get active workflows."""
        workflows = agent.workflows or {}
        lines = ["# Active Workflows", ""]
        
        if not workflows:
            lines.append("No active workflows.")
            return "\n".join(lines)
        
        for wf_id, state in workflows.items():
            status = getattr(state, 'status', 'unknown')
            lines.append(f"- {wf_id}: {status}")
        
        return "\n".join(lines)

    @mcp.resource("agent://factory-cross-ref")
    def agent_factory_cross_ref() -> str:
        """Cross-reference with other factory bricks."""
        return """# Agent Factory Integration

## Related Bricks

### kb (Knowledge Base)
- RAG: Agents query KB for context
- Document ingestion via agent workflows

### workflow
- Agent tasks as workflow steps
- Long-running agent jobs

### telemetry
- Agent execution metrics
- Strands hooks for observability

### events
- Agent completion events
- Swarm handoff notifications

### auth
- Agent authorization
- Tool access control

## Integration Patterns

1. **RAG Agent**: Query KB before reasoning
2. **Workflow Agent**: Agent as workflow executor
3. **Observable Agent**: Telemetry hooks for tracing
4. **Event-Driven**: Emit events on completion
"""
