"""Flet action_pane renderer — expandable action forms.

Returns real ft.Control instances.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from ..models import UIComponent


def render_action_pane(c: UIComponent) -> ft.Control:
    """Render action_pane as ExpansionPanelList with embedded forms."""
    p = c.props
    actions = p.get("actions", [])

    panels = []
    for action in actions:
        fields = action.get("fields", [])
        field_controls = [_render_action_field(f) for f in fields]
        field_controls.append(
            ft.Button(
                content=ft.Text(action.get("label", "Submit")),
                icon=ft.Icons.PLAY_ARROW,
            )
        )
        panels.append(ft.ExpansionPanel(
            header=ft.ListTile(
                title=ft.Text(action.get("label", "Action")),
                subtitle=ft.Text(action.get("tool", ""), size=11,
                                 color=ft.Colors.ON_SURFACE_VARIANT),
            ),
            content=ft.Container(
                content=ft.Column(field_controls, spacing=12),
                padding=16,
            ),
        ))

    if not panels:
        return ft.Text("No actions available", size=13,
                       color=ft.Colors.ON_SURFACE_VARIANT)

    return ft.ExpansionPanelList(controls=panels)


def _render_action_field(field: dict[str, Any]) -> ft.Control:
    """Render a single action field."""
    field_type = field.get("type", "text")
    label = field.get("label", field.get("name", ""))

    if field_type == "select":
        options = field.get("options", [])
        dd_options = []
        for o in options:
            if isinstance(o, dict):
                dd_options.append(ft.dropdown.Option(
                    key=o.get("value", ""), text=o.get("label", "")))
            else:
                dd_options.append(ft.dropdown.Option(key=str(o), text=str(o)))
        return ft.Dropdown(label=label, options=dd_options)

    if field_type == "range":
        return ft.Slider(
            min=field.get("min", 0), max=field.get("max", 100),
            value=field.get("value", 50), label=label,
        )

    return ft.TextField(
        label=label,
        hint_text=field.get("placeholder", ""),
        multiline=field_type == "textarea",
        min_lines=3 if field_type == "textarea" else 1,
        tooltip=field.get("tooltip"),
    )
