"""OpenArcade base — public Python API.

The base composes the wall (projects/openarcade/wall) and the control-plane
bricks (launch, library, arcade_config, state, curator, ui) into a single
installable unit. Lean-deps contract: ``import factory.openarcade`` does NOT
pull ``fastmcp`` — the MCP server is loaded on demand via
``factory.openarcade.server.create_mcp_server``.

MCP surface: ``from factory.openarcade.server import create_mcp_server``.
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[5]
_PROJECT_ROOT = _REPO_ROOT / "projects" / "openarcade"
if _PROJECT_ROOT.exists() and str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from factory.curator.interface import (
    CompatReport,
    CompatStatus,
    RomCandidate,
    check_compatibility,
    scan_rom_directory,
)
from factory.launch.interface import (
    GetStatusProbe,
    LaunchConfig,
    MockNciTransport,
    NciCommand,
    NciState,
    NciStatus,
    NciTransport,
    UdpNciTransport,
    VersionProbe,
    parse_status,
)

from .app import build_app, run_wall
from .env import resolve_config_dir, resolve_nci_target
from .types import ControlsVM, GameTile

__all__ = [
    "build_app",
    "run_wall",
    "NciTransport",
    "GetStatusProbe",
    "GameTile",
    "ControlsVM",
    "NciCommand",
    "NciState",
    "NciStatus",
    "parse_status",
    "UdpNciTransport",
    "MockNciTransport",
    "LaunchConfig",
    "VersionProbe",
    "RomCandidate",
    "scan_rom_directory",
    "CompatReport",
    "CompatStatus",
    "check_compatibility",
    "resolve_config_dir",
    "resolve_nci_target",
]
