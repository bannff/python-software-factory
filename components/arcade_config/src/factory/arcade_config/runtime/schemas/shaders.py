"""Curated shader presets — honest reference data for the user's real decision set.

NOT a dir scan (presets are not pulled locally — disk-restricted).
Pure data, no IO.
"""

from __future__ import annotations

# Canonical presets available on RetroPie + RetroArch (Pi 4 / x86).
# Ordered by common use. "None" = shader disabled.
SHADER_PRESETS: tuple[str, ...] = (
    "None",
    "crt-pi",
    "crt-geom",
    "crt-easymode",
    "crt-hyllian",
    "lcd-grid",
    "sharp-bilinear-2x-prescale",
)
