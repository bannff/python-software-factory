"""Extended Flet renderers — hero, tabs, breadcrumbs, modal, toast.

Returns real ft.Control instances.
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..models import UIComponent


def render_hero(c: UIComponent) -> ft.Control:
    """Render hero component as a gradient banner."""
    p = c.props
    return ft.Container(
        content=ft.Column(
            [
                ft.Text(p.get("title", ""), size=32,
                        weight=ft.FontWeight.BOLD, color=ft.Colors.WHITE),
                ft.Text(p.get("subtitle", ""), size=16,
                        color=ft.Colors.WHITE_70),
            ],
            alignment=ft.MainAxisAlignment.CENTER,
            horizontal_alignment=ft.CrossAxisAlignment.CENTER,
        ),
        gradient=ft.LinearGradient(
            colors=[ft.Colors.DEEP_PURPLE, ft.Colors.INDIGO],
            begin=ft.Alignment(-1, -1),
            end=ft.Alignment(1, 1),
        ),
        padding=40,
        border_radius=16,
        width=float("inf"),
    )


def render_tabs(
    c: UIComponent, render_child: Callable[[UIComponent], ft.Control],
) -> ft.Control:
    """Render tabs component as ft.Tabs."""
    p = c.props
    tabs_data = p.get("tabs", [])
    flet_tabs = []
    for tab in tabs_data:
        content = ft.Text(tab.get("label", "Tab"), size=14)
        flet_tabs.append(ft.Tab(
            label=tab.get("label", "Tab"),
            content=ft.Container(content=content, padding=16),
        ))
    return ft.Tabs(content=flet_tabs, length=len(flet_tabs),
                   animation_duration=300)


def render_breadcrumbs(c: UIComponent) -> ft.Control:
    """Render breadcrumbs as a Row of text links."""
    p = c.props
    items = p.get("items", [])
    parts: list[ft.Control] = []
    for i, item in enumerate(items):
        label = item.get("label", str(item)) if isinstance(item, dict) else str(item)
        parts.append(ft.Text(label, size=13, color=ft.Colors.PRIMARY))
        if i < len(items) - 1:
            parts.append(ft.Text(" / ", size=13, color=ft.Colors.OUTLINE))
    return ft.Row(controls=parts, spacing=4)


def render_modal(c: UIComponent) -> ft.Control:
    """Render modal as a Card placeholder (actual dialog needs page ref)."""
    p = c.props
    return ft.Card(
        content=ft.Container(
            content=ft.Column([
                ft.Text(p.get("title", "Modal"), size=18,
                        weight=ft.FontWeight.BOLD),
                ft.Text(p.get("content", ""), size=14),
            ]),
            padding=20,
        ),
        elevation=4,
    )


def render_toast(c: UIComponent) -> ft.Control:
    """Render toast as a styled Container (SnackBar needs page ref)."""
    p = c.props
    return ft.Container(
        content=ft.Row([
            ft.Icon(ft.Icons.INFO, color=ft.Colors.WHITE, size=18),
            ft.Text(p.get("message", ""), color=ft.Colors.WHITE),
        ]),
        bgcolor=ft.Colors.INVERSE_SURFACE,
        border_radius=8,
        padding=12,
    )
