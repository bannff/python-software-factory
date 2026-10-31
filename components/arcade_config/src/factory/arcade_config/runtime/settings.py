"""Resolved runtime settings from layered RetroArch configs. Pure — no IO."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class RetroArchRuntimeSettings:
    """Resolved, display-ready runtime settings for a game/system context."""

    core: str
    run_ahead_enabled: bool
    run_ahead_frames: int
    shader_enabled: bool
    shader_name: str
    video_smooth: bool


def _parse_bool(raw: str) -> bool:
    return raw.strip().lower() == "true"


def _shader_basename(path: str) -> str:
    """Extract shader preset name without extension from a full path.

    Example: "/opt/retropie/.../crt-pi.glslp" -> "crt-pi"
    """
    if not path:
        return ""
    base = os.path.basename(path)
    name, _ = os.path.splitext(base)
    return name


def resolve_runtime_settings(
    *cfg_layers: dict[str, str],
    core: str = "",
) -> RetroArchRuntimeSettings:
    """Merge config layers left-to-right (later wins) and resolve typed settings.

    Parameters
    ----------
    *cfg_layers : dict[str, str]
        Parsed RetroArch config dicts (from parse_cfg). Ordered from least to most
        specific (global, system, game). Later values override earlier.
    core : str
        Core identifier (from emulators.cfg or equivalent). Passed through as-is.
    """
    merged: dict[str, str] = {}
    for layer in cfg_layers:
        merged.update(layer)

    run_ahead_enabled = _parse_bool(merged.get("run_ahead_enabled", "false"))
    run_ahead_frames = max(0, int(merged.get("run_ahead_frames", "1") or "1"))

    shader_path = merged.get("video_shader", "")
    shader_enable_raw = _parse_bool(merged.get("video_shader_enable", "false"))
    # Shader is truly enabled only if the flag is on AND a path exists.
    shader_enabled = shader_enable_raw and bool(shader_path.strip())
    shader_name = _shader_basename(shader_path) if shader_enabled else ""

    video_smooth = _parse_bool(merged.get("video_smooth", "false"))

    return RetroArchRuntimeSettings(
        core=core,
        run_ahead_enabled=run_ahead_enabled,
        run_ahead_frames=run_ahead_frames,
        shader_enabled=shader_enabled,
        shader_name=shader_name,
        video_smooth=video_smooth,
    )
