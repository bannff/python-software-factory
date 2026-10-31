"""Flet graph_viewer renderer — interactive force-directed graph.

Uses Canvas for drawing, InteractiveViewer for pan/zoom,
and networkx spring_layout for positions.
"""

from __future__ import annotations

from typing import Any

import flet as ft
import flet.canvas as cv

from ..models import UIComponent

STATUS_COLORS: dict[str, str] = {
    "running": ft.Colors.BLUE_400,
    "completed": ft.Colors.GREEN_400,
    "failed": ft.Colors.RED_400,
    "error": ft.Colors.RED_400,
    "pending": ft.Colors.OUTLINE,
}
TYPE_COLORS: dict[str, str] = {
    "person": ft.Colors.BLUE_400,
    "organization": ft.Colors.GREEN_400,
    "concept": ft.Colors.PURPLE_400,
    "document": ft.Colors.ORANGE_400,
    "event": ft.Colors.RED_400,
    "location": ft.Colors.TEAL_400,
}
_DEFAULT_CLR = ft.Colors.BLUE_200
_EDGE_CLR = ft.Colors.OUTLINE_VARIANT
_CANVAS_W, _CANVAS_H = 800, 600


def render_graph_viewer(c: UIComponent) -> ft.Control:
    """Render graph_viewer with Canvas + InteractiveViewer.

    Supports two data formats:
    - Legacy: entities/relationships props (from graph brick data_tool)
    - Inline: data.nodes/data.edges props (from session graph events)
    """
    p = c.props
    # Support inline data prop (session-scoped graphs)
    inline = p.get("data", {})
    if inline and isinstance(inline, dict) and inline.get("nodes"):
        entities = [{"id": n["id"], "type": n.get("type", ""),
                     "color": n.get("color")} for n in inline["nodes"]]
        rels = [{"source": e["source"], "target": e["target"]}
                for e in inline.get("edges", [])]
    else:
        entities = p.get("entities", [])
        rels = p.get("relationships", [])
    node_size = p.get("node_size", 20)
    show_labels = p.get("show_labels", True)

    if not entities:
        return _empty_state()

    positions = _compute_layout(entities, rels)
    shapes = _build_shapes(entities, rels, positions, node_size, show_labels)
    canvas = cv.Canvas(shapes=shapes, width=_CANVAS_W, height=_CANVAS_H)
    viewer = ft.InteractiveViewer(
        min_scale=0.2, max_scale=5.0, content=canvas,
        boundary_margin=ft.margin.all(20),
    )
    legend = _build_legend(entities)
    return ft.Column([viewer, legend], spacing=8, expand=True)


def _empty_state() -> ft.Control:
    return ft.Container(
        content=ft.Column([
            ft.Icon(ft.Icons.HUB, size=48, color=ft.Colors.OUTLINE),
            ft.Text("No entities found", size=16,
                    color=ft.Colors.ON_SURFACE_VARIANT),
            ft.Text("Use the graph tools to ingest data", size=12,
                    color=ft.Colors.OUTLINE),
        ], alignment=ft.MainAxisAlignment.CENTER,
           horizontal_alignment=ft.CrossAxisAlignment.CENTER),
        padding=40, width=float("inf"),
    )


def _compute_layout(
    entities: list[dict], rels: list[dict],
) -> dict[str, tuple[float, float]]:
    """Compute positions via networkx spring_layout (fallback: circular)."""
    try:
        import networkx as nx
    except ImportError:
        return _fallback_layout(entities)

    G = nx.Graph()
    for e in entities:
        G.add_node(e.get("id", str(e)))
    for r in rels:
        src = r.get("source_id", r.get("source", ""))
        tgt = r.get("target_id", r.get("target", ""))
        if src and tgt:
            G.add_edge(src, tgt)

    raw = nx.spring_layout(G, k=2.0, iterations=50, scale=1.0)
    margin = 60
    w, h = _CANVAS_W - 2 * margin, _CANVAS_H - 2 * margin
    return {
        nid: (margin + (x + 1) / 2 * w, margin + (y + 1) / 2 * h)
        for nid, (x, y) in raw.items()
    }


def _fallback_layout(entities: list[dict]) -> dict[str, tuple[float, float]]:
    import math
    n = max(len(entities), 1)
    cx, cy = _CANVAS_W / 2, _CANVAS_H / 2
    r = min(cx, cy) * 0.7
    return {
        e.get("id", str(i)): (
            cx + r * math.cos(2 * math.pi * i / n),
            cy + r * math.sin(2 * math.pi * i / n),
        )
        for i, e in enumerate(entities)
    }


def _build_shapes(
    entities: list[dict], rels: list[dict],
    positions: dict[str, tuple[float, float]],
    node_size: int, show_labels: bool,
) -> list[cv.Shape]:
    shapes: list[cv.Shape] = []
    edge_paint = ft.Paint(color=_EDGE_CLR, stroke_width=1.5,
                          style=ft.PaintingStyle.STROKE)
    # Edges first (behind nodes)
    for r in rels:
        src = r.get("source_id", r.get("source", ""))
        tgt = r.get("target_id", r.get("target", ""))
        if src in positions and tgt in positions:
            x1, y1 = positions[src]
            x2, y2 = positions[tgt]
            shapes.append(cv.Line(x1, y1, x2, y2, paint=edge_paint))

    emap = {e.get("id", str(i)): e for i, e in enumerate(entities)}
    for nid, (x, y) in positions.items():
        ent = emap.get(nid, {})
        etype = ent.get("type", ent.get("entity_type", ""))
        # Per-node color (session status) takes priority over type color
        node_color = ent.get("color") or STATUS_COLORS.get(etype) or TYPE_COLORS.get(etype, _DEFAULT_CLR)
        fill = ft.Paint(color=node_color, style=ft.PaintingStyle.FILL)
        shapes.append(cv.Circle(x, y, node_size, paint=fill))
        if show_labels:
            tp = ft.Paint(color=ft.Colors.ON_SURFACE,
                          style=ft.PaintingStyle.FILL)
            shapes.append(cv.Text(
                x - node_size, y + node_size + 12,
                text=str(nid)[:16],
                style=ft.TextStyle(size=10), max_width=node_size * 4,
                paint=tp,
            ))
    return shapes


def _build_legend(entities: list[dict]) -> ft.Control:
    types_seen: dict[str, str] = {}
    for e in entities:
        t = e.get("type", e.get("entity_type", ""))
        if t and t not in types_seen:
            types_seen[t] = TYPE_COLORS.get(t, _DEFAULT_CLR)
    chips = [
        ft.Container(
            content=ft.Row([
                ft.Container(width=12, height=12, bgcolor=color,
                             border_radius=6),
                ft.Text(label, size=11),
            ], spacing=4),
        )
        for label, color in types_seen.items()
    ]
    return ft.Row(controls=chips, spacing=12, wrap=True) if chips else ft.Container()
