"""Complex Flet control renderers — table, metric, card, list, alert, chart.

Form rendering extracted to flet_renderers_form.py.
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


def render_table(c: UIComponent) -> ft.Control:
    """Render table with alternating row colors and styled header."""
    props = c.props
    columns = props.get("columns", [])
    rows = props.get("rows", props.get("data", []))
    dt_columns = [
        ft.DataColumn(ft.Text(
            (col.get("label", col) if isinstance(col, dict) else str(col)),
            weight=ft.FontWeight.W_600, size=12, color=_TERTIARY,
        ))
        for col in columns
    ]
    dt_rows = []
    for i, row in enumerate(rows):
        cells_data = row if isinstance(row, (list, tuple)) else [row]
        cells = [ft.DataCell(ft.Text(str(cell), size=13)) for cell in cells_data]
        dt_rows.append(ft.DataRow(
            cells=cells, color=_SURFACE_VARIANT if i % 2 == 0 else None,
        ))
    return ft.Container(
        content=ft.DataTable(
            columns=dt_columns, rows=dt_rows,
            border=ft.Border.all(1, _OUTLINE), border_radius=10,
            heading_row_color=_SURFACE_VARIANT, data_row_max_height=48,
        ),
        border_radius=10,
    )


_ICON_MAP = {
    "chart": ft.Icons.BAR_CHART, "list": ft.Icons.LIST,
    "document": ft.Icons.DESCRIPTION, "users": ft.Icons.PEOPLE,
    "shield": ft.Icons.SHIELD, "default": ft.Icons.ANALYTICS,
}


def _change_color(change: str) -> str:
    if change.startswith("+"):
        return "#66BB6A"
    return ft.Colors.ERROR if change.startswith("-") else ft.Colors.ON_SURFACE_VARIANT


def render_metric(c: UIComponent) -> ft.Control:
    """Render metric card with icon and optional change indicator."""
    p = c.props
    change = p.get("change", "")
    icon_name = _ICON_MAP.get(p.get("icon", "default"), ft.Icons.ANALYTICS)
    children = [
        ft.Row([
            ft.Icon(icon_name, size=18, color=_SECONDARY),
            ft.Text(p.get("label", "Metric"), size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT),
        ], spacing=6),
        ft.Text(str(p.get("value", "—")), size=28, weight=ft.FontWeight.BOLD),
    ]
    if change:
        children.append(ft.Text(change, size=11, color=_change_color(change)))
    return ft.Container(
        content=ft.Column(children, spacing=4),
        bgcolor=_SURFACE_VARIANT, border=ft.Border.all(1, _OUTLINE),
        border_radius=12,
        padding=ft.Padding.symmetric(vertical=14, horizontal=16),
        animate=ft.Animation(400, ft.AnimationCurve.EASE_OUT),
    )


def render_alert(c: UIComponent) -> ft.Control:
    """Render alert with severity-based left border accent."""
    p = c.props
    severity = p.get("severity", "info")
    colors = {"info": _SECONDARY, "success": "#66BB6A",
              "warning": "#FFA726", "error": "#FF5252"}
    icons = {"info": ft.Icons.INFO, "success": ft.Icons.CHECK_CIRCLE,
             "warning": ft.Icons.WARNING, "error": ft.Icons.ERROR}
    accent = colors.get(severity, _SECONDARY)
    return ft.Container(
        content=ft.Row([
            ft.Icon(icons.get(severity, ft.Icons.INFO), color=accent),
            ft.Text(p.get("message", p.get("text", "")), expand=True, size=13),
        ], spacing=10),
        bgcolor=_SURFACE_VARIANT,
        border=ft.Border.only(left=ft.BorderSide(3, accent)),
        border_radius=8, padding=14,
    )


def render_list(c: UIComponent) -> ft.Control:
    """Render list with styled tiles and leading icons."""
    items = c.props.get("items", [])
    tiles = []
    for item in items:
        if isinstance(item, dict):
            tiles.append(ft.ListTile(
                title=ft.Text(item.get("title", str(item)), size=13),
                subtitle=(ft.Text(item.get("subtitle", ""), size=11)
                          if item.get("subtitle") else None),
                leading=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=_SECONDARY),
            ))
        else:
            tiles.append(ft.ListTile(
                title=ft.Text(str(item), size=13),
                leading=ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=_SECONDARY),
            ))
    return ft.ListView(controls=tiles, spacing=4, padding=8)


def render_chart(c: UIComponent) -> ft.Control:
    """Render chart placeholder icon card."""
    p = c.props
    chart_type = p.get("chart_type", "bar")
    icons = {"line": ft.Icons.SHOW_CHART, "bar": ft.Icons.BAR_CHART,
             "pie": ft.Icons.PIE_CHART, "area": ft.Icons.AREA_CHART,
             "scatter": ft.Icons.SCATTER_PLOT}
    return ft.Container(
        content=ft.Column([
            ft.Icon(icons.get(chart_type, ft.Icons.INSERT_CHART),
                    size=48, color=_SECONDARY),
            ft.Text(p.get("title", f"{chart_type.title()} Chart"), size=14),
        ], alignment=ft.MainAxisAlignment.CENTER,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=_SURFACE_VARIANT, border=ft.Border.all(1, _OUTLINE),
        border_radius=10, padding=16, height=p.get("height", 200),
    )


def render_card(
    c: UIComponent, render_child: Callable[[UIComponent], ft.Control],
) -> ft.Control:
    """Render card with styled container and children."""
    p = c.props
    children_rendered = [render_child(child) for child in c.children]
    title_elems = []
    if p.get("title"):
        title_elems.append(
            ft.Text(p["title"], size=16, weight=ft.FontWeight.W_600))
    return ft.Container(
        content=ft.Column(title_elems + children_rendered, spacing=10),
        bgcolor=_SURFACE_VARIANT, border=ft.Border.all(1, _OUTLINE),
        border_radius=12, padding=18,
    )
