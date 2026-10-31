"""Interactive Flet renderers — code_block, timeline, stat_grid, tree_view, live_feed.

Returns real ft.Control instances.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from ..models import UIComponent


def render_code_block(c: UIComponent) -> ft.Control:
    """Render code_block as ft.Markdown with code fence."""
    p = c.props
    code = p.get("code", p.get("content", ""))
    lang = p.get("language", "python")
    md_text = f"```{lang}\n{code}\n```"
    return ft.Markdown(
        value=md_text,
        selectable=True,
        extension_set=ft.MarkdownExtensionSet.GITHUB_FLAVORED,
    )


def render_timeline(c: UIComponent) -> ft.Control:
    """Render timeline as a vertical list of events."""
    p = c.props
    events = p.get("events", p.get("items", []))
    tiles = []
    for ev in events:
        title = ev.get("title", str(ev)) if isinstance(ev, dict) else str(ev)
        subtitle = ev.get("time", ev.get("subtitle", "")) if isinstance(ev, dict) else ""
        tiles.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.CIRCLE, size=12, color=ft.Colors.PRIMARY),
            title=ft.Text(title, size=14),
            subtitle=ft.Text(str(subtitle), size=11) if subtitle else None,
        ))
    return ft.ListView(controls=tiles, spacing=4, padding=8)


def render_stat_grid(c: UIComponent) -> ft.Control:
    """Render stat_grid as a responsive grid of metric cards."""
    p = c.props
    stats = p.get("stats", p.get("items", []))
    cards = []
    for stat in stats:
        cards.append(ft.Card(
            content=ft.Container(
                content=ft.Column([
                    ft.Text(stat.get("label", ""), size=12,
                            color=ft.Colors.ON_SURFACE_VARIANT),
                    ft.Text(str(stat.get("value", "—")), size=24,
                            weight=ft.FontWeight.BOLD),
                ], spacing=4),
                padding=12,
            ),
            elevation=1,
        ))
    return ft.GridView(controls=cards, runs_count=3, spacing=8, run_spacing=8)


def render_tree_view(c: UIComponent) -> ft.Control:
    """Render tree_view as nested ExpansionPanelList."""
    p = c.props
    nodes = p.get("nodes", p.get("items", []))
    panels = []
    for node in nodes:
        label = node.get("label", str(node)) if isinstance(node, dict) else str(node)
        children_data = node.get("children", []) if isinstance(node, dict) else []
        child_controls = [
            ft.ListTile(title=ft.Text(
                ch.get("label", str(ch)) if isinstance(ch, dict) else str(ch),
                size=13,
            ))
            for ch in children_data
        ]
        body = ft.Column(child_controls) if child_controls else ft.Text("(empty)")
        panels.append(ft.ExpansionPanel(
            header=ft.ListTile(title=ft.Text(label)),
            content=ft.Container(content=body, padding=ft.padding.only(left=24)),
        ))
    return ft.ExpansionPanelList(controls=panels)


def render_live_feed(c: UIComponent) -> ft.Control:
    """Render live_feed as a scrollable list with refresh indicator."""
    p = c.props
    items = p.get("items", [])
    tiles = []
    for item in items:
        text = item.get("text", str(item)) if isinstance(item, dict) else str(item)
        tiles.append(ft.ListTile(
            leading=ft.Icon(ft.Icons.FIBER_MANUAL_RECORD, size=10,
                            color=ft.Colors.GREEN),
            title=ft.Text(text, size=13),
        ))
    if not tiles:
        tiles.append(ft.Text("No feed items", size=13,
                             color=ft.Colors.ON_SURFACE_VARIANT))
    return ft.ListView(controls=tiles, spacing=4, padding=8, auto_scroll=True)
