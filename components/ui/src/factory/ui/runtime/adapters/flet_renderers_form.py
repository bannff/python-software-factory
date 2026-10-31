"""Flet form renderer — styled form fields with cybersecurity aesthetic.

Extracted from flet_renderers_complex.py to stay under 200 LOC.
Handles form, select, range, text, textarea, and password fields.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from ..models import UIComponent
from . import flet_palette as P

_PRIMARY = P.PRIMARY
_SECONDARY = P.SECONDARY
_TERTIARY = P.TERTIARY
_SURFACE_VARIANT = P.SURFACE_VARIANT
_OUTLINE = P.OUTLINE


def render_form(c: UIComponent) -> ft.Control:
    """Render form component with polished styling."""
    p = c.props
    fields = p.get("fields", [])
    controls = [_render_form_field(f) for f in fields]
    controls.append(
        ft.Button(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.SEND, size=16, color=ft.Colors.WHITE),
                    ft.Text(
                        p.get("submit_label", "Submit"),
                        weight=ft.FontWeight.W_600,
                        color=ft.Colors.WHITE,
                    ),
                ],
                spacing=8,
                alignment=ft.MainAxisAlignment.CENTER,
            ),
            bgcolor=_PRIMARY,
            style=ft.ButtonStyle(
                shape=ft.RoundedRectangleBorder(radius=10),
                padding=ft.Padding.symmetric(vertical=14, horizontal=24),
            ),
        )
    )
    return ft.Container(
        content=ft.Column(controls=controls, spacing=14),
        bgcolor=_SURFACE_VARIANT,
        border=ft.Border.all(1, _OUTLINE),
        border_radius=12,
        padding=20,
    )


def _render_form_field(field: dict[str, Any]) -> ft.Control:
    """Render a single form field with enhanced styling."""
    field_type = field.get("type", "text")
    label = field.get("label", field.get("name", ""))

    if field_type == "select":
        return _render_select(field, label)
    if field_type == "range":
        return _render_range(field, label)
    return _render_text_field(field, field_type, label)


def _render_select(field: dict[str, Any], label: str) -> ft.Control:
    """Render a styled dropdown select."""
    options = field.get("options", [])
    dd_options = []
    for o in options:
        if isinstance(o, dict):
            dd_options.append(
                ft.dropdown.Option(key=o.get("value", ""), text=o.get("label", ""))
            )
        else:
            dd_options.append(ft.dropdown.Option(key=str(o), text=str(o)))
    return ft.Dropdown(
        label=label,
        options=dd_options,
        border_color=_OUTLINE,
        focused_border_color=_PRIMARY,
        border_radius=10,
        tooltip=field.get("tooltip"),
    )


def _render_range(field: dict[str, Any], label: str) -> ft.Control:
    """Render a styled range slider with label."""
    return ft.Column(
        [
            ft.Text(label, size=12, color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Slider(
                min=field.get("min", 0),
                max=field.get("max", 100),
                value=field.get("value", 50),
                label="{value}",
                active_color=_PRIMARY,
                inactive_color=_OUTLINE,
            ),
        ],
        spacing=4,
    )


def _render_text_field(
    field: dict[str, Any], field_type: str, label: str,
) -> ft.Control:
    """Render a styled text/textarea/password field."""
    return ft.TextField(
        label=label,
        hint_text=field.get("placeholder", ""),
        password=field_type == "password",
        multiline=field_type == "textarea",
        min_lines=3 if field_type == "textarea" else 1,
        tooltip=field.get("tooltip"),
        border_color=_OUTLINE,
        focused_border_color=_PRIMARY,
        cursor_color=_TERTIARY,
        border_radius=10,
    )
