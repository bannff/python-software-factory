"""Pure serializers: model <-> RetroArch text format. No IO."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping

from .models import CoreOption, InputRemap, ShaderPreset

_CFG_LINE = re.compile(r'^(\S+)\s*=\s*"(.*)"$')


def parse_cfg(text: str) -> dict[str, str]:
    """Parse RetroArch key = "value" lines. Skips non-matching. Last-dup wins."""
    result: dict[str, str] = {}
    for line in text.splitlines():
        m = _CFG_LINE.match(line.strip())
        if m:
            result[m.group(1)] = m.group(2)
    return result


def serialize_cfg(pairs: Mapping[str, str]) -> str:
    """Serialize key-value pairs to RetroArch .cfg format (key = "value")."""
    lines = [f'{k} = "{v}"' for k, v in pairs.items()]
    return "\n".join(lines) + "\n" if lines else ""


def serialize_core_options(options: Iterable[CoreOption]) -> str:
    """Serialize core options to .opt format (key = "value")."""
    lines = [f'{opt.key} = "{opt.value}"' for opt in options]
    return "\n".join(lines) + "\n" if lines else ""


def serialize_remap(remaps: Iterable[InputRemap]) -> str:
    """Serialize input remaps to .rmp format.

    Format: input_player1_btn = "target"
    (RetroArch remap key convention per R-RA research).
    """
    lines = [f'input_player1_{r.retropad_button} = "{r.target}"' for r in remaps]
    return "\n".join(lines) + "\n" if lines else ""


def serialize_shader_ref(preset: ShaderPreset) -> str:
    """Serialize shader preset reference as cfg lines."""
    return (
        f'video_shader_enable = "true"\n'
        f'video_shader = "{preset.path}"\n'
    )
