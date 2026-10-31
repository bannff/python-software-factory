"""Typer CLI for OpenArcade — headless ops.

Subcommands:
- ``run``    — launch the wall (delegates to ``run_wall``)
- ``scan``   — scan a ROM directory, print + persist a JSON report
- ``launch`` — send an NCI launch command for a single game id
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Optional

import typer

from .env import resolve_config_dir, resolve_nci_target

app = typer.Typer(
    name="openarcade",
    help="OpenArcade headless ops — run, scan, launch.",
    no_args_is_help=True,
    add_completion=False,
)


def _print_json(payload: dict) -> None:
    typer.echo(json.dumps(payload, indent=2, sort_keys=True, default=str))


@app.command()
def run(
    config_dir: Optional[Path] = typer.Option(
        None, "--config-dir", help="Override OPENARCADE_CONFIG_DIR."
    ),
    nci_host: Optional[str] = typer.Option(
        None, "--nci-host", help="Override OPENARCADE_NCI_HOST."
    ),
    nci_port: Optional[int] = typer.Option(
        None, "--nci-port", help="Override OPENARCADE_NCI_PORT."
    ),
) -> None:
    """Launch the OpenArcade wall (native Flet window)."""
    host, port = resolve_nci_target(nci_host, nci_port)
    import os

    os.environ["OPENARCADE_NCI_HOST"] = host
    os.environ["OPENARCADE_NCI_PORT"] = str(port)
    from .app import run_wall

    run_wall(config_dir=config_dir)


@app.command()
def scan(
    rom_dir: Path = typer.Argument(..., exists=True, file_okay=False, dir_okay=True),
    config_dir: Optional[Path] = typer.Option(
        None, "--config-dir", help="Where to write the scan report."
    ),
) -> None:
    """Scan a ROM directory and write a JSON report under the config dir."""
    import os

    if os.environ.get("OPENARCADE_NO_FIXTURES") == "1":
        typer.echo("OPENARCADE_NO_FIXTURES=1: skipping fixture tree", err=True)
    from factory.curator.interface import scan_rom_directory

    resolved_cfg = resolve_config_dir(config_dir)
    candidates = list(scan_rom_directory(rom_dir))
    summary = {
        "rom_dir": str(rom_dir),
        "config_dir": str(resolved_cfg),
        "count": len(candidates),
        "candidates": [
            {
                "path": str(c.path),
                "system": c.system,
                "sha1": c.sha1,
                "size": c.size,
            }
            for c in candidates
        ],
    }
    _print_json(summary)
    report_path = resolved_cfg / "scan_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str))
    typer.echo(f"\nwrote {report_path}", err=True)


@app.command()
def launch(
    game_id: str = typer.Argument(..., help="Tile id (e.g. 'contra', 'mk')."),
    config_dir: Optional[Path] = typer.Option(
        None, "--config-dir", help="Override OPENARCADE_CONFIG_DIR."
    ),
    nci_host: Optional[str] = typer.Option(
        None, "--nci-host", help="Override OPENARCADE_NCI_HOST."
    ),
    nci_port: Optional[int] = typer.Option(
        None, "--nci-port", help="Override OPENARCADE_NCI_PORT."
    ),
    timeout: float = typer.Option(
        5.0, "--timeout", help="Seconds to wait for PLAYING state."
    ),
) -> None:
    """Send an NCI launch command and wait for the game to enter PLAYING."""
    import os

    from factory.launch.interface import (
        GetStatusProbe,
        NciCommand,
        UdpNciTransport,
    )

    host, port = resolve_nci_target(nci_host, nci_port)
    os.environ["OPENARCADE_NCI_HOST"] = host
    os.environ["OPENARCADE_NCI_PORT"] = str(port)
    resolve_config_dir(config_dir)

    transport = UdpNciTransport(host=host, port=port)
    transport.send(NciCommand.LOAD_GAME, payload=game_id)
    probe = GetStatusProbe(transport=transport, timeout=0.5)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        status = probe.poll()
        if status.state.value == "PLAYING":
            _print_json({"game_id": game_id, "state": "PLAYING", "target": f"{host}:{port}"})
            raise typer.Exit(0)
        time.sleep(0.1)
    _print_json({"game_id": game_id, "state": "TIMEOUT", "target": f"{host}:{port}"})
    raise typer.Exit(1)


def main() -> None:
    """Entry point for the ``openarcade`` console script."""
    app()


if __name__ == "__main__":
    sys.exit(main())
