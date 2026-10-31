"""Pure merge: partitions raw disk options into curated CoreOption + uncurated RawOption.

No IO. Reuses parse_cfg for reading .opt (same key="value" format).
"""

from __future__ import annotations

from .models import CoreOption, RawOption


def build_core_options(
    raw: dict[str, str],
    schema: dict[str, tuple[str, tuple[str, ...]]],
) -> tuple[list[CoreOption], list[RawOption]]:
    """Partition raw key-value pairs from disk against a curated schema.

    Curated keys -> CoreOption (with allowed choices from schema).
    IMPORTANT: if the live value is NOT in the curated allowed tuple, APPEND it
    to allowed before constructing — disk is truth, never raise.

    Uncurated keys -> RawOption (read-only display).

    Returns:
        (curated_options, raw_options) — stable ordering follows schema then remainder.
    """
    curated: list[CoreOption] = []
    raw_options: list[RawOption] = []

    # First pass: curated keys in schema order
    consumed: set[str] = set()
    for key, (_, allowed) in schema.items():
        if key in raw:
            consumed.add(key)
            value = raw[key]
            if value not in allowed:
                # Disk is truth — append the live value
                allowed = (*allowed, value)
        else:
            # Not overridden yet — show the core's default (libretro: first choice)
            # so every curated option is always visible and settable.
            value = allowed[0]
        curated.append(CoreOption(key=key, value=value, allowed=allowed))

    # Second pass: uncurated keys in disk order
    for key, value in raw.items():
        if key not in consumed:
            raw_options.append(RawOption(key=key, value=value))

    return curated, raw_options
