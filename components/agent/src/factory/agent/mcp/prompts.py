"""MCP prompts for agent module."""

from __future__ import annotations

from typing import Any


def register(mcp: Any) -> None:
    """Register agent prompts."""

    @mcp.prompt()
    def agent_invoke_swarm(
        swarm_id: str = "default",
        task: str = "your task description",
    ) -> str:
        """Guide for invoking a swarm."""
        return f"""Help me invoke a swarm for a task.

Swarm ID: {swarm_id}
Task: {task}

Please:
1. Check the swarm exists (get_swarm_registry)
2. Review the swarm configuration
3. Invoke the swarm with appropriate context
4. Monitor and report results

Use invoke_swarm tool when ready."""

    @mcp.prompt()
    def agent_create_swarm(
        task_description: str = "describe your multi-agent task",
    ) -> str:
        """Guide for creating a new swarm configuration."""
        return f"""Help me design a swarm for this task:

{task_description}

Please guide me through:
1. Identifying required agent roles
2. Defining system prompts for each agent
3. Selecting appropriate tools
4. Setting handoff rules
5. Configuring the swarm

Consider the polymorphic design - use framework-agnostic configs."""

    @mcp.prompt()
    def agent_invoke_graph(
        graph_id: str = "default",
        task: str = "your task description",
    ) -> str:
        """Guide for invoking a graph workflow."""
        return f"""Help me invoke a graph workflow.

Graph ID: {graph_id}
Task: {task}

Please:
1. Check the graph exists (get_graph_registry)
2. Review the graph structure
3. Invoke the graph with context
4. Track execution through nodes

Use invoke_graph tool when ready."""

    @mcp.prompt()
    def agent_reason(
        task: str = "your reasoning task",
    ) -> str:
        """Guide for dynamic reasoning orchestration."""
        return f"""Help me with dynamic reasoning.

Task: {task}

The reason tool will:
1. Analyze the task complexity
2. Select appropriate execution strategy
3. Route to swarm, graph, or direct execution
4. Return synthesized results

Use the reason tool for automatic orchestration."""

    @mcp.prompt()
    def agent_health_check() -> str:
        """Guide for checking agent system health."""
        return """Help me check the agent system health.

Please:
1. Run health_check for overall status
2. Check agent registry
3. Check swarm registry
4. Check graph registry
5. Review any active workflows

Start with health_check tool."""

    @mcp.prompt()
    def agent_workflow_status(
        workflow_id: str = "workflow-id",
    ) -> str:
        """Guide for checking workflow status."""
        return f"""Help me check workflow status.

Workflow ID: {workflow_id}

Please:
1. Get workflow status (get_workflow_status)
2. Check progress and state
3. Report any errors
4. Suggest next steps if incomplete

Use get_workflow_status tool."""

    @mcp.prompt()
    def agent_langchain_setup() -> str:
        """Guide for configuring the LangChain and LangGraph agent runtime."""
        return """Help me configure the LangChain and LangGraph agent runtime.

Please guide me through:
1. Selecting a provider profile through llm_gateway
2. Resolving the model with the LangChain model factory
3. Scoping MCP v2 tools for the persona
4. Configuring LangGraph checkpointing and thread identity
5. Testing one streamed typed tool call

Use the Agent registry and provider profiles; do not introduce another runtime."""
