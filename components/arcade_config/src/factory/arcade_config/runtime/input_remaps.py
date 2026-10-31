"""Pure builder: partitions raw .rmp key-value pairs into InputRemap objects.

No IO. Mirrors build_core_options — renders ALL RetroPad buttons at IDENTITY
default (button->button), with live overrides from raw winning.
"""

from __future__ import annotations

from .models import RETROPAD_BUTTONS, InputRemap

# Canonical button order (stable, matches libretro spec layout)
RETROPAD_BUTTON_ORDER: tuple[str, ...] = (
    "b", "y", "select", "start",
    "up", "down", "left", "right",
    "a", "x", "l", "r",
    "l2", "r2", "l3", "r3",
)


def build_input_remaps(
    raw: dict[str, str],
    buttons: tuple[str, ...] = RETROPAD_BUTTON_ORDER,
) -> list[InputRemap]:
    """Build a complete 16-button remap list from raw .rmp key-value pairs.

    .rmp format: keys are ``input_player1_<btn> = "<target>"``
    The `raw` dict passed in should already be parsed by parse_cfg; keys are
    the FULL key strings. This function strips the ``input_player1_`` prefix
    to recover the button name.

    Algorithm (mirrors build_core_options render-all-at-default):
    - Every button in `buttons` gets an InputRemap entry.
    - If the button has a live override in `raw`, the target is that override value.
    - Otherwise, the target is IDENTITY (button maps to itself).

    Returns:
        List of InputRemap in canonical button order.
    """
    # Parse raw: strip prefix, collect overrides
    PREFIX = "input_player1_"
    overrides: dict[str, str] = {}
    for key, value in raw.items():
        if key.startswith(PREFIX):
            btn = key[len(PREFIX):]
            # Strip surrounding quotes if present (parse_cfg strips them, but be defensive)
            target = value.strip('"')
            overrides[btn] = target

    result: list[InputRemap] = []
    for btn in buttons:
        target = overrides.get(btn, btn)  # identity default
        # Validate: target must be a valid button (illegal state unrepresentable)
        if target not in RETROPAD_BUTTONS:
            # Disk is truth for core_options, but for remaps an invalid target
            # is nonsensical. Fall back to identity rather than crash the UI.
            target = btn
        result.append(InputRemap(retropad_button=btn, target=target))

    return result
