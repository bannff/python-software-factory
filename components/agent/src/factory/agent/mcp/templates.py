"""Prompt templates for agent module."""

AGENT_CONFIG_TEMPLATE = """
# Agent Configuration: {agent_name}

## Details
ID: {agent_id}
Model: {model}

## System Prompt
{system_prompt}

## Tools
{tools}
"""

SWARM_CONFIG_TEMPLATE = """
# Swarm Configuration: {swarm_id}

## Agents
{agents}

## Settings
Entry Point: {entry_point}
Max Handoffs: {max_handoffs}
Max Iterations: {max_iterations}

## Task
{task}
"""

SWARM_RESULT_TEMPLATE = """
# Swarm Result

## Status: {status}

## Output
{output}

## Execution
Time: {execution_time}s
Nodes: {node_count}

## History
{node_history}
"""

GRAPH_CONFIG_TEMPLATE = """
# Graph Configuration: {graph_id}

## Nodes
{nodes}

## Edges
{edges}

## Entry Point
{entry_point}
"""

REASONING_TEMPLATE = """
# Reasoning Task

## Task
{task}

## Context
{context}

## Approach
{approach}

## Result
{result}
"""

TEMPLATES = {
    "agent-config": AGENT_CONFIG_TEMPLATE,
    "swarm-config": SWARM_CONFIG_TEMPLATE,
    "swarm-result": SWARM_RESULT_TEMPLATE,
    "graph-config": GRAPH_CONFIG_TEMPLATE,
    "reasoning": REASONING_TEMPLATE,
}


def get_template(name: str) -> str | None:
    """Get template by name."""
    return TEMPLATES.get(name)


def list_templates() -> list[str]:
    """List available templates."""
    return list(TEMPLATES.keys())


def render_template(name: str, **kwargs: str) -> str | None:
    """Render a template with provided values."""
    template = TEMPLATES.get(name)
    if template is None:
        return None
    try:
        return template.format(**kwargs)
    except KeyError:
        return template
