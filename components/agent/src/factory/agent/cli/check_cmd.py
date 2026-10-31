"""Check command - validate configuration files."""

import asyncio
import click


@click.command()
@click.option("--config", "-c", default="./config", help="Path to config directory")
def check(config: str) -> None:
    """Validate configuration files."""
    asyncio.run(_check_config(config))


async def _check_config(config: str) -> None:
    """Run configuration validation."""
    from factory.agent import SuperAgent

    agent = SuperAgent(config_dir=config)
    click.echo(f"Checking configuration in: {config}")

    try:
        await agent.initialize()
        click.echo("")
        click.echo("✓ Configuration valid")
        click.echo("")
        _report_registries(agent)
    except Exception as e:
        click.echo(f"✗ Configuration error: {e}")
        raise SystemExit(1)


def _report_registries(agent) -> None:
    """Report loaded registries."""
    if agent.agent_registry:
        click.echo(f"Agents ({len(agent.agent_registry.agents)}):")
        for agent_id in agent.agent_registry.agents:
            click.echo(f"  - {agent_id}")

    if agent.swarm_registry:
        click.echo(f"\nSwarms ({len(agent.swarm_registry.swarms)}):")
        for swarm_id in agent.swarm_registry.swarms:
            click.echo(f"  - {swarm_id}")

    if agent.graph_registry:
        click.echo(f"\nGraphs ({len(agent.graph_registry.graphs)}):")
        for graph_id in agent.graph_registry.graphs:
            click.echo(f"  - {graph_id}")

    if agent.tool_registry:
        click.echo(f"\nTools ({len(agent.tool_registry.tools)}):")
        for tool_name in agent.tool_registry.tools:
            click.echo(f"  - {tool_name}")
