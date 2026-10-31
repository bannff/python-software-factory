"""Flet chart renderer using flet-charts native controls.

Supports BarChart, LineChart, PieChart, ScatterChart.
Requires: pip install flet-charts
"""

from __future__ import annotations

from typing import Any

import flet as ft

from ..models import UIComponent

_PALETTE = [
    ft.Colors.BLUE, ft.Colors.GREEN, ft.Colors.ORANGE,
    ft.Colors.PURPLE, ft.Colors.RED, ft.Colors.TEAL,
    ft.Colors.AMBER, ft.Colors.CYAN,
]


def render_chart_native(c: UIComponent) -> ft.Control:
    """Render chart using flet-charts native controls."""
    try:
        import flet_charts  # noqa: F401
    except ImportError:
        return _fallback_chart(c)
    p = c.props
    chart_type = p.get("chart_type", "bar")
    match chart_type:
        case "line":
            return _build_line_chart(p)
        case "pie":
            return _build_pie_chart(p)
        case "scatter":
            return _build_scatter_chart(p)
        case _:
            return _build_bar_chart(p)


def _fallback_chart(c: UIComponent) -> ft.Control:
    """Placeholder when flet-charts not installed."""
    p = c.props
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.BAR_CHART, size=48),
            ft.Text(p.get("title", "Chart"), size=14),
            ft.Text("Install flet-charts for native charts", size=11,
                    color=ft.Colors.ON_SURFACE_VARIANT),
        ], alignment=ft.MainAxisAlignment.CENTER,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        bgcolor=ft.Colors.SURFACE_CONTAINER, border_radius=8,
        padding=16, height=p.get("height", 200),
    )


def _build_bar_chart(p: dict[str, Any]) -> ft.Control:
    import flet_charts as fc
    data = p.get("data", [])
    groups = []
    for i, item in enumerate(data):
        value = float(item.get("value", 0))
        color = _PALETTE[i % len(_PALETTE)]
        groups.append(fc.BarChartGroup(
            x=i, rods=[fc.BarChartRod(
                from_y=0, to_y=value, width=24,
                color=color, border_radius=4,
                tooltip=f"{item.get('label', i)}: {value}",
            )],
        ))
    labels = [
        fc.ChartAxisLabel(value=i, label=ft.Text(
            item.get("label", str(i)), size=10))
        for i, item in enumerate(data)
    ]
    return fc.BarChart(
        groups=groups,
        bottom_axis=fc.ChartAxis(labels=labels, label_size=32),
        left_axis=fc.ChartAxis(label_size=40),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        horizontal_grid_lines=fc.ChartGridLines(
            color=ft.Colors.OUTLINE_VARIANT, width=0.5),
        max_y=_max_y(data),
        height=p.get("height", 250),
        animation=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        expand=True,
    )


def _build_line_chart(p: dict[str, Any]) -> ft.Control:
    import flet_charts as fc
    data = p.get("data", [])
    points = [
        fc.LineChartDataPoint(x=float(i), y=float(item.get("value", 0)))
        for i, item in enumerate(data)
    ]
    series = fc.LineChartData(
        points=points, stroke_width=3,
        color=ft.Colors.BLUE, curved=True,
    )
    return fc.LineChart(
        data_series=[series],
        left_axis=fc.ChartAxis(label_size=40),
        bottom_axis=fc.ChartAxis(label_size=32),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        height=p.get("height", 250),
        animation=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        expand=True,
    )


def _build_pie_chart(p: dict[str, Any]) -> ft.Control:
    import flet_charts as fc
    data = p.get("data", [])
    sections = []
    for i, item in enumerate(data):
        value = float(item.get("value", 0))
        label = item.get("label", str(i))
        color = _PALETTE[i % len(_PALETTE)]
        sections.append(fc.PieChartSection(
            value=value, title=f"{label}\n{value}",
            color=color, radius=80,
            title_style=ft.TextStyle(size=10),
        ))
    return fc.PieChart(
        sections=sections, center_space_radius=40,
        sections_space=2, height=p.get("height", 250),
        animation=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        expand=True,
    )


def _build_scatter_chart(p: dict[str, Any]) -> ft.Control:
    import flet_charts as fc
    data = p.get("data", [])
    spots = []
    for i, item in enumerate(data):
        x = float(item.get("x", i))
        y = float(item.get("y", item.get("value", 0)))
        color = _PALETTE[i % len(_PALETTE)]
        spots.append(fc.ScatterChartSpot(x=x, y=y, radius=6, color=color))
    return fc.ScatterChart(
        spots=spots,
        left_axis=fc.ChartAxis(label_size=40),
        bottom_axis=fc.ChartAxis(label_size=32),
        border=ft.Border.all(1, ft.Colors.OUTLINE),
        height=p.get("height", 250),
        animation=ft.Animation(500, ft.AnimationCurve.EASE_OUT),
        expand=True,
    )


def _max_y(data: list[dict[str, Any]]) -> float:
    vals = [float(d.get("value", 0)) for d in data]
    return max(vals) * 1.2 if vals else 10
