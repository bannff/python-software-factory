"""Composition helpers — assembles the DI container the wall needs.

The wall's existing ``Navigator`` already builds itself from a tuple of
config / launch / curator primitives; this module is the auditable seam
where the base declares which classes it wires together. Today the wall does
the wiring inline; the spec calls for a ``build_di_container(config_dir)``
function that returns the assembled pieces so tests and the headless CLI can
swap them out.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import NamedTuple

from .env import resolve_config_dir, resolve_nci_target


class Container(NamedTuple):
    """Assembled DI pieces the wall needs to boot.

    Each field is intentionally typed loosely — the wall's existing
    constructor signatures accept concrete classes, and importing them here
    would drag Flet into the lean import path. Tests should construct this
    with fakes/mocks for the headless CLI flow.
    """

    config_dir: Path
    nci_host: str
    nci_port: int


def build_di_container(config_dir: Path | str | None = None) -> Container:
    """Build the DI container from the base's env contract."""
    port_env = os.environ.get("OPENARCADE_NCI_PORT")
    host_env = os.environ.get("OPENARCADE_NCI_HOST")
    host, port = resolve_nci_target(
        host_env,
        int(port_env) if port_env is not None else None,
    )
    return Container(
        config_dir=resolve_config_dir(config_dir),
        nci_host=host,
        nci_port=port,
    )
