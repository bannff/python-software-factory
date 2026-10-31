"""Flet control renderers for basic UI components.

Maps UIComponent types to real ft.Control instances.
Split into:
- flet_renderers.py: Layout helpers + basic controls (text, button, image)
- flet_renderers_complex.py: Complex controls (table, form, card, chart)
"""

from __future__ import annotations

from typing import Any, Callable

import flet as ft

from ..models import UIComponent

from .flet_renderers_complex import (
    render_table, render_metric, render_alert,
    render_list, render_chart, render_card,
)
from .flet_renderers_form import render_form

SIZE_MAP = {"sm": 12, "md": 14, "lg": 18, "xl": 24, "2xl": 32}


def layout_to_container(layout_type: str) -> str:
    """Map layout type to Flet container control name."""
    return {"column": "Column", "row": "Row", "grid": "GridView",
            "stack": "Stack", "wrap": "Wrap"}.get(layout_type, "Column")


def make_layout_control(
    layout_type: str, children: list[ft.Control],
) -> ft.Control:
    """Create a Flet layout control from type string and children."""
    match layout_type:
        case "row":
            return ft.Row(controls=children, wrap=True)
        case "grid":
            return ft.GridView(controls=children, runs_count=2)
        case "stack":
            return ft.Stack(controls=children)
        case _:
            return ft.Column(controls=children, spacing=16)


def render_text(c: UIComponent) -> ft.Control:
    """Render text component as ft.Text."""
    p = c.props
    size = SIZE_MAP.get(p.get("size", "md"), 14)
    weight = ft.FontWeight.BOLD if p.get("bold") else None
    return ft.Text(
        value=p.get("content", p.get("text", "")),
        size=size, weight=weight,
        italic=p.get("italic", False), color=p.get("color"),
    )


def render_button(c: UIComponent) -> ft.Control:
    """Render button component as Flet button."""
    p = c.props
    variant = p.get("variant", "filled")
    label = p.get("label", p.get("text", "Button"))
    icon, disabled = p.get("icon"), p.get("disabled", False)
    content = ft.Text(label)
    match variant:
        case "outlined":
            return ft.OutlinedButton(content=content, icon=icon, disabled=disabled)
        case "text":
            return ft.TextButton(content=content, icon=icon, disabled=disabled)
        case "icon":
            return ft.IconButton(icon=icon or ft.Icons.CIRCLE, disabled=disabled)
        case _:
            return ft.Button(content=content, icon=icon, disabled=disabled)


def render_image(c: UIComponent) -> ft.Control:
    """Render image component as ft.Image."""
    p = c.props
    return ft.Image(
        src=p.get("src", p.get("url", "")),
        width=p.get("width"), height=p.get("height"),
        fit="contain",
        border_radius=p.get("border_radius", 0),
    )


def render_progress(c: UIComponent) -> ft.Control:
    """Render progress as ft.ProgressBar or ft.ProgressRing."""
    p = c.props
    value = p.get("value", 0)
    max_val = p.get("max", 100)
    progress = value / max_val if max_val > 0 else 0
    if p.get("circular", False):
        return ft.ProgressRing(value=progress if progress < 1 else None)
    return ft.ProgressBar(value=progress, bar_height=p.get("height", 4))


def render_custom(c: UIComponent) -> ft.Control:
    """Render custom/unknown component as placeholder."""
    return ft.Container(
        content=ft.Text(f"Custom: {c.component_type.value}", size=12),
        padding=8, border=ft.Border.all(1, ft.Colors.OUTLINE), border_radius=8,
    )
