"""Flet page renderer — 3-zone layout (hero, info+controls, output).

Renders the standardized `page` and `composed_page` component types
with cybersecurity-themed visual hierarchy.
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..models import UIComponent
from . import flet_palette as P

_PRIMARY = P.PRIMARY
_SECONDARY = P.SECONDARY
_TERTIARY = P.TERTIARY
_SURFACE_VARIANT = P.SURFACE_VARIANT
_OUTLINE = P.OUTLINE

# Tailwind gradient → Flet color mapping
_GRADIENT_MAP: dict[str, list[str]] = {
    "from-blue-500 to-cyan-500": [_SECONDARY, _TERTIARY],
    "from-teal-500 to-cyan-600": [ft.Colors.TEAL, _TERTIARY],
    "from-emerald-500 to-teal-500": ["#66BB6A", ft.Colors.TEAL],
    "from-teal-500 to-green-500": [ft.Colors.TEAL, "#66BB6A"],
    "from-green-500 to-emerald-600": ["#66BB6A", ft.Colors.TEAL],
    "from-purple-500 to-indigo-500": [_PRIMARY, "#5C6BC0"],
    "from-indigo-500 to-blue-500": ["#5C6BC0", _SECONDARY],
    "from-red-500 to-orange-500": ["#FF5252", "#FF7043"],
    "from-orange-500 to-amber-500": ["#FF7043", "#FFB74D"],
    "from-pink-500 to-rose-500": [ft.Colors.PINK, "#FF5252"],
}


def _parse_gradient(gradient_str: str) -> list[str]:
    return _GRADIENT_MAP.get(gradient_str, [_PRIMARY, _SECONDARY])


def render_page(
    c: UIComponent, render_child: Callable[[UIComponent], ft.Control],
) -> ft.Control:
    """Render the 3-zone page layout with polished visual hierarchy."""
    p = c.props

    # Zone 1: Hero banner
    hero = ft.Container(
        content=ft.Column(
            [
                ft.Text(p.get("icon", ""), size=36),
                ft.Text(
                    p.get("title", ""),
                    size=26,
                    weight=ft.FontWeight.BOLD,
                    color=ft.Colors.WHITE,
                ),
                ft.Text(
                    p.get("subtitle", ""),
                    size=13,
                    color=ft.Colors.WHITE_70,
                ),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            spacing=6,
        ),
        gradient=ft.LinearGradient(
            colors=_parse_gradient(p.get("gradient", "")),
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
        ),
        padding=ft.Padding.symmetric(vertical=28, horizontal=24),
        border_radius=16,
        border=ft.Border.all(1, _OUTLINE),
        animate=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
    )

    # Zone 2: Info (metrics) left + Controls (forms) right
    info = [render_child(ch) for ch in c.children
            if ch.props.get("zone") == "info"]
    ctrls = [render_child(ch) for ch in c.children
             if ch.props.get("zone") == "controls"]

    zone2 = ft.Container()
    if info or ctrls:
        zone2 = ft.ResponsiveRow(
            [
                ft.Column(
                    info, col={"sm": 12, "md": 6}, spacing=10,
                ),
                ft.Column(
                    ctrls, col={"sm": 12, "md": 6}, spacing=10,
                ),
            ],
        )

    # Zone 3: Output (everything else)
    output = [render_child(ch) for ch in c.children
              if ch.props.get("zone") not in ("info", "controls")]
    if p.get("output_layout") == "two-column" and len(output) >= 2:
        zone3 = ft.ResponsiveRow(
            [ft.Container(content=ctrl, col={"sm": 12, "lg": 6})
             for ctrl in output],
            spacing=16,
        )
    else:
        zone3 = ft.Column(output, spacing=16) if output else ft.Container()

    return ft.Column(
        [hero, zone2, zone3],
        spacing=20,
        scroll=ft.ScrollMode.AUTO,
        expand=True,
    )


def render_composed_page(
    c: UIComponent, render_child: Callable[[UIComponent], ft.Control],
) -> ft.Control:
    """Render composed_page as a styled column of children."""
    children = [render_child(ch) for ch in c.children]
    return ft.Column(
        children, spacing=16, scroll=ft.ScrollMode.AUTO, expand=True,
    )
