"""Curated snes9x core option schema — real libretro snes9x options.

Pure frozen data. Each entry: option_key -> (human_label, allowed_choices).
Reference: libretro snes9x core options documentation.
"""

SNES9X_CORE_OPTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "snes9x_region": (
        "Console Region",
        ("Auto", "NTSC", "PAL"),
    ),
    "snes9x_aspect": (
        "Preferred Aspect Ratio",
        ("4:3", "8:7", "Uncorrected", "Auto"),
    ),
    "snes9x_overclock_superfx": (
        "SuperFX Overclocking",
        ("100%", "150%", "200%", "250%", "300%", "400%", "500%"),
    ),
    "snes9x_overclock_cycles": (
        "Reduce Slowdown (Hack, Unsafe)",
        ("disabled", "light", "compatible", "max"),
    ),
    "snes9x_blargg": (
        "Blargg NTSC Filter",
        ("disabled", "monochrome", "rf", "composite", "s-video", "rgb"),
    ),
    "snes9x_hires_blend": (
        "Hires Blending",
        ("disabled", "merge", "blur"),
    ),
    "snes9x_audio_interpolation": (
        "Audio Interpolation",
        ("gaussian", "cubic", "sinc", "none", "linear"),
    ),
    "snes9x_layer_1": (
        "Show Layer 1",
        ("enabled", "disabled"),
    ),
    "snes9x_layer_2": (
        "Show Layer 2",
        ("enabled", "disabled"),
    ),
    "snes9x_layer_3": (
        "Show Layer 3",
        ("enabled", "disabled"),
    ),
    "snes9x_layer_4": (
        "Show Layer 4",
        ("enabled", "disabled"),
    ),
    "snes9x_layer_5": (
        "Show Sprite Layer",
        ("enabled", "disabled"),
    ),
    "snes9x_gfx_clip": (
        "Enable Graphic Clip Windows",
        ("enabled", "disabled"),
    ),
    "snes9x_gfx_transp": (
        "Enable Transparency Effects",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_1": (
        "Enable Sound Channel 1",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_2": (
        "Enable Sound Channel 2",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_3": (
        "Enable Sound Channel 3",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_4": (
        "Enable Sound Channel 4",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_5": (
        "Enable Sound Channel 5",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_6": (
        "Enable Sound Channel 6",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_7": (
        "Enable Sound Channel 7",
        ("enabled", "disabled"),
    ),
    "snes9x_sndchan_8": (
        "Enable Sound Channel 8",
        ("enabled", "disabled"),
    ),
    "snes9x_block_invalid_vram_access": (
        "Block Invalid VRAM Access",
        ("enabled", "disabled"),
    ),
    "snes9x_echo_buffer_hack": (
        "Echo Buffer Hack (Unsafe, only for old addmusic)",
        ("disabled", "enabled"),
    ),
}
