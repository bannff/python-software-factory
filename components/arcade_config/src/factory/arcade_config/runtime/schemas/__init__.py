"""Core option schema registry. Maps core name -> curated option definitions."""

from .snes9x import SNES9X_CORE_OPTIONS
from .shaders import SHADER_PRESETS

# Registry: core_name -> dict[option_key, (human_label, allowed_choices)]
CORE_OPTION_SCHEMAS: dict[str, dict[str, tuple[str, tuple[str, ...]]]] = {
    "lr-snes9x2002": SNES9X_CORE_OPTIONS,
    "snes9x_libretro": SNES9X_CORE_OPTIONS,
    "snes9x2002_libretro": SNES9X_CORE_OPTIONS,
}

__all__ = ["CORE_OPTION_SCHEMAS", "SHADER_PRESETS", "SNES9X_CORE_OPTIONS"]
