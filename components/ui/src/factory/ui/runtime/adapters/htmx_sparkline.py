"""Inline SVG sparkline renderer for metric components.

Renders a tiny polyline chart from a list of numeric values.
Used by the metric renderer when a `sparkline` prop is provided.
"""

from __future__ import annotations


def render_sparkline(data: list, intent: str = "") -> str:
    """Render an inline SVG sparkline from a list of numeric values.

    Args:
        data: List of numbers to plot.
        intent: Semantic intent for color (critical/success/warning).

    Returns:
        HTML string with an inline SVG, or empty string if insufficient data.
    """
    if not data or len(data) < 2:
        return ""
    nums = [float(v) for v in data if isinstance(v, (int, float))]
    if len(nums) < 2:
        return ""
    lo, hi = min(nums), max(nums)
    span = hi - lo or 1
    w, h = 48, 16
    step = w / (len(nums) - 1)
    points = " ".join(
        f"{i * step:.1f},{h - (v - lo) / span * h:.1f}"
        for i, v in enumerate(nums)
    )
    color_map = {
        "critical": "var(--er)",
        "success": "var(--su)",
        "warning": "var(--wa)",
    }
    color = (
        f"oklch({color_map[intent]})"
        if intent in color_map
        else "oklch(var(--p))"
    )
    return (
        f'<svg class="sparkline" width="{w}" height="{h}"'
        f' viewBox="0 0 {w} {h}">'
        f'<polyline fill="none" stroke="{color}" stroke-width="1.5"'
        f' stroke-linecap="round" stroke-linejoin="round"'
        f' points="{points}"/></svg>'
    )
