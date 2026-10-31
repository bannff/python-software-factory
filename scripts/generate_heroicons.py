#!/usr/bin/env python3
"""Download Heroicons 24/outline SVGs and generate Python data files.

Fetches all 292 Heroicons from the official GitHub repo, extracts
path `d` attributes, and writes them as Python dicts split across
three data files to stay under 200 lines each.

Usage:
    python scripts/generate_heroicons.py

No external dependencies — uses only stdlib (urllib, re, pathlib).
"""
from __future__ import annotations

import re
import urllib.request
from pathlib import Path

BASE_URL = (
    "https://raw.githubusercontent.com/tailwindlabs/heroicons"
    "/master/src/24/outline/{name}.svg"
)

OUT_DIR = Path(
    "components/ui/src/factory/ui/runtime/adapters"
)

# fmt: off
ICON_NAMES: list[str] = [
    "academic-cap", "adjustments-horizontal", "adjustments-vertical",
    "archive-box-arrow-down", "archive-box-x-mark", "archive-box",
    "arrow-down-circle", "arrow-down-left", "arrow-down-on-square-stack",
    "arrow-down-on-square", "arrow-down-right", "arrow-down-tray",
    "arrow-down", "arrow-left-circle", "arrow-left-end-on-rectangle",
    "arrow-left-on-rectangle", "arrow-left-start-on-rectangle",
    "arrow-left", "arrow-long-down", "arrow-long-left",
    "arrow-long-right", "arrow-long-up", "arrow-path-rounded-square",
    "arrow-path", "arrow-right-circle", "arrow-right-end-on-rectangle",
    "arrow-right-on-rectangle", "arrow-right-start-on-rectangle",
    "arrow-right", "arrow-small-down", "arrow-small-left",
    "arrow-small-right", "arrow-small-up", "arrow-top-right-on-square",
    "arrow-trending-down", "arrow-trending-up", "arrow-turn-down-left",
    "arrow-turn-down-right", "arrow-turn-left-down",
    "arrow-turn-left-up", "arrow-turn-right-down",
    "arrow-turn-right-up", "arrow-turn-up-left", "arrow-turn-up-right",
    "arrow-up-circle", "arrow-up-left", "arrow-up-on-square-stack",
    "arrow-up-on-square", "arrow-up-right", "arrow-up-tray",
    "arrow-up", "arrow-uturn-down", "arrow-uturn-left",
    "arrow-uturn-right", "arrow-uturn-up", "arrows-pointing-in",
    "arrows-pointing-out", "arrows-right-left", "arrows-up-down",
    "at-symbol", "backspace", "backward", "banknotes", "bars-2",
    "bars-3-bottom-left", "bars-3-bottom-right", "bars-3-center-left",
    "bars-3", "bars-4", "bars-arrow-down", "bars-arrow-up",
    "battery-0", "battery-100", "battery-50", "beaker", "bell-alert",
    "bell-slash", "bell-snooze", "bell", "bold", "bolt-slash", "bolt",
    "book-open", "bookmark-slash", "bookmark-square", "bookmark",
    "briefcase", "bug-ant", "building-library", "building-office-2",
    "building-office", "building-storefront", "cake", "calculator",
    "calendar-date-range", "calendar-days", "calendar", "camera",
    "chart-bar-square", "chart-bar", "chart-pie",
    "chat-bubble-bottom-center-text", "chat-bubble-bottom-center",
    "chat-bubble-left-ellipsis", "chat-bubble-left-right",
    "chat-bubble-left", "chat-bubble-oval-left-ellipsis",
    "chat-bubble-oval-left", "check-badge", "check-circle", "check",
    "chevron-double-down", "chevron-double-left",
    "chevron-double-right", "chevron-double-up", "chevron-down",
    "chevron-left", "chevron-right", "chevron-up-down", "chevron-up",
    "circle-stack", "clipboard-document-check",
    "clipboard-document-list", "clipboard-document", "clipboard",
    "clock", "cloud-arrow-down", "cloud-arrow-up", "cloud",
    "code-bracket-square", "code-bracket", "cog-6-tooth", "cog-8-tooth",
    "cog", "command-line", "computer-desktop", "cpu-chip",
    "credit-card", "cube-transparent", "cube",
    "currency-bangladeshi", "currency-dollar", "currency-euro",
    "currency-pound", "currency-rupee", "currency-yen",
    "cursor-arrow-rays", "cursor-arrow-ripple", "device-phone-mobile",
    "device-tablet", "divide", "document-arrow-down",
    "document-arrow-up", "document-chart-bar", "document-check",
    "document-currency-bangladeshi", "document-currency-dollar",
    "document-currency-euro", "document-currency-pound",
    "document-currency-rupee", "document-currency-yen",
    "document-duplicate", "document-magnifying-glass", "document-minus",
    "document-plus", "document-text", "document",
    "ellipsis-horizontal-circle", "ellipsis-horizontal",
    "ellipsis-vertical", "envelope-open", "envelope", "equals",
    "exclamation-circle", "exclamation-triangle", "eye-dropper",
    "eye-slash", "eye", "face-frown", "face-smile", "film",
    "finger-print", "fire", "flag", "folder-arrow-down", "folder-minus",
    "folder-open", "folder-plus", "folder", "forward", "funnel", "gif",
    "gift-top", "gift", "globe-alt", "globe-americas",
    "globe-asia-australia", "globe-europe-africa", "h1", "h2", "h3",
    "hand-raised", "hand-thumb-down", "hand-thumb-up", "hashtag",
    "heart", "home-modern", "home", "identification",
    "inbox-arrow-down", "inbox-stack", "inbox", "information-circle",
    "italic", "key", "language", "lifebuoy", "light-bulb", "link-slash",
    "link", "list-bullet", "lock-closed", "lock-open",
    "magnifying-glass-circle", "magnifying-glass-minus",
    "magnifying-glass-plus", "magnifying-glass", "map-pin", "map",
    "megaphone", "microphone", "minus-circle", "minus-small", "minus",
    "moon", "musical-note", "newspaper", "no-symbol", "numbered-list",
    "paint-brush", "paper-airplane", "paper-clip", "pause-circle",
    "pause", "pencil-square", "pencil", "percent-badge",
    "phone-arrow-down-left", "phone-arrow-up-right", "phone-x-mark",
    "phone", "photo", "play-circle", "play-pause", "play",
    "plus-circle", "plus-small", "plus", "power",
    "presentation-chart-bar", "presentation-chart-line", "printer",
    "puzzle-piece", "qr-code", "question-mark-circle", "queue-list",
    "radio", "receipt-percent", "receipt-refund", "rectangle-group",
    "rectangle-stack", "rocket-launch", "rss", "scale", "scissors",
    "server-stack", "server", "share", "shield-check",
    "shield-exclamation", "shopping-bag", "shopping-cart",
    "signal-slash", "signal", "slash", "sparkles", "speaker-wave",
    "speaker-x-mark", "square-2-stack", "square-3-stack-3d",
    "squares-2x2", "squares-plus", "star", "stop-circle", "stop",
    "strikethrough", "sun", "swatch", "table-cells", "tag", "ticket",
    "trash", "trophy", "truck", "tv", "underline", "user-circle",
    "user-group", "user-minus", "user-plus", "user", "users",
    "variable", "video-camera-slash", "video-camera", "view-columns",
    "viewfinder-circle", "wallet", "wifi", "window",
    "wrench-screwdriver", "wrench", "x-circle", "x-mark",
]
# fmt: on

PATH_RE = re.compile(r'<path[^>]*?\bd="([^"]+)"', re.DOTALL)


def fetch_icon(name: str) -> list[str]:
    """Download one SVG and return its path d-attribute strings."""
    url = BASE_URL.format(name=name)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            svg = resp.read().decode()
    except Exception as exc:
        print(f"  WARN: {name} – {exc}")
        return []
    return PATH_RE.findall(svg)


def write_data_file(path: Path, icons: dict[str, list[str]]) -> None:
    """Write a Python module with an ICONS dict."""
    lines: list[str] = [
        '"""Heroicons path data (generated — do not edit)."""',
        "",
        "ICONS: dict[str, list[str]] = {",
    ]
    for name, paths in sorted(icons.items()):
        if len(paths) == 1:
            lines.append(f'    "{name}": ["{paths[0]}"],')
        else:
            parts = ", ".join(f'"{p}"' for p in paths)
            lines.append(f'    "{name}": [{parts}],')
    lines.append("}")
    lines.append("")
    path.write_text("\n".join(lines))
    print(f"  wrote {path}  ({len(lines)} lines, {len(icons)} icons)")


def main() -> None:
    print("Fetching Heroicons 24/outline …")
    all_icons: dict[str, list[str]] = {}
    for i, name in enumerate(ICON_NAMES, 1):
        paths = fetch_icon(name)
        if paths:
            all_icons[name] = paths
        if i % 25 == 0:
            print(f"  {i}/{len(ICON_NAMES)} fetched")
    print(f"  total: {len(all_icons)} icons")

    # Split into three roughly equal chunks by sorted name
    sorted_names = sorted(all_icons)
    chunk = len(sorted_names) // 3
    slices = [
        sorted_names[:chunk],
        sorted_names[chunk : chunk * 2],
        sorted_names[chunk * 2 :],
    ]
    suffixes = ["a", "d", "m"]

    for suffix, names in zip(suffixes, slices):
        subset = {n: all_icons[n] for n in names}
        out = OUT_DIR / f"heroicons_data_{suffix}.py"
        write_data_file(out, subset)

    print("Done.")


if __name__ == "__main__":
    main()
