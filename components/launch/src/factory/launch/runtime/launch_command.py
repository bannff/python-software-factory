"""Pure command builder for RetroArch process launch.

Decides what to execute. Does not act. The proven spike recipe:
  retroarch -L <core> <rom> --appendconfig <cfg>
where cfg enables NCI network_cmd + optional video_driver override.

platform_launch_argv wraps this with macOS `open -a` on Darwin (exec'ing the
inner binary directly exits 0 WITHOUT launching — LaunchServices requires `open`).
"""

from __future__ import annotations

import os
import platform
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class LaunchConfig:
    """Immutable launch parameters. core is NON-OPTIONAL (illegal state unrepresentable)."""

    core: str
    rom: str
    retroarch_bin: str = "retroarch"
    port: int = 55355
    video_driver: str | None = None


def build_override_cfg_text(cfg: LaunchConfig) -> str:
    """Build the override config text (appended via --appendconfig).

    Always: network_cmd_enable + network_cmd_port.
    Conditionally: video_driver (only when not None — e.g. 'metal' on macOS).
    """
    lines = [
        'network_cmd_enable = "true"',
        f'network_cmd_port = "{cfg.port}"',
    ]
    if cfg.video_driver is not None:
        lines.append(f'video_driver = "{cfg.video_driver}"')
    return "\n".join(lines) + "\n"


def build_launch_argv(cfg: LaunchConfig, cfg_path: str | Path) -> list[str]:
    """Build the full argv for subprocess exec (raw, no platform wrapper).

    Returns: [bin, -L, core, rom, --appendconfig, cfg_path]
    """
    return [
        cfg.retroarch_bin,
        "-L",
        cfg.core,
        cfg.rom,
        "--appendconfig",
        str(cfg_path),
    ]


def platform_launch_argv(cfg: LaunchConfig, cfg_path: str | Path) -> list[str]:
    """Build the platform-correct exec argv.

    On macOS: `open -a <RetroArch.app> --args -L <core> <rom> --appendconfig <cfg>`
    (exec'ing the inner Mach-O binary directly exits 0 without launching the GUI).

    On Linux: raw `retroarch -L <core> <rom> --appendconfig <cfg>`.
    """
    base = build_launch_argv(cfg, cfg_path)
    if platform.system() == "Darwin":
        app = os.environ.get("OPENARCADE_RETROARCH_APP", "/Applications/RetroArch.app")
        # base[0] is the inner binary; `open -a` handles it.
        return ["open", "-a", app, "--args", *base[1:]]
    return base


def is_darwin_trampoline(argv: list[str]) -> bool:
    """Detect whether argv uses the macOS `open` trampoline.

    Used by ProcessLaunchOrchestrator to decide readiness-over-liveness behavior.
    """
    return bool(argv) and argv[0].endswith("open")
