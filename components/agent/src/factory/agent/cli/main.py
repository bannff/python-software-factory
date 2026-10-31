"""CLI entry point and group definition."""

import click

from .init_cmd import init
from .run_cmd import run
from .check_cmd import check


@click.group()
@click.version_option(version="0.1.0")
def cli() -> None:
    """Super Agent CLI - portable multi-agent orchestration."""
    pass


# Register commands
cli.add_command(init)
cli.add_command(run)
cli.add_command(check)


if __name__ == "__main__":
    cli()
