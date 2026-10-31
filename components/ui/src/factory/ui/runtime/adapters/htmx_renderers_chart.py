"""HTMX renderer for Chart.js canvas components.

Extracted from htmx_renderers_page.py to keep files under 200 LOC.
Renders bar, line, pie, doughnut, and area charts via Chart.js.
"""

from __future__ import annotations

from ..models import UIComponent

_PALETTE = [
    "rgba(99, 102, 241, 0.6)", "rgba(34, 197, 94, 0.6)",
    "rgba(234, 179, 8, 0.6)", "rgba(239, 68, 68, 0.6)",
    "rgba(6, 182, 212, 0.6)", "rgba(168, 85, 247, 0.6)",
]
_BORDER = [c.replace("0.6", "1") for c in _PALETTE]


def render_chart_js(c: UIComponent) -> str:
    """Render a Chart.js canvas with data from props."""
    p = c.props
    ct = p.get("chart_type", "bar")
    title = p.get("title", "")
    labels = p.get("labels", [])
    datasets = p.get("datasets", [])
    height = p.get("height", "h-64")
    canvas_id = f"chart-{c.id}"

    ds_js = []
    for i, ds in enumerate(datasets):
        color = ds.get("color", _PALETTE[i % len(_PALETTE)])
        border = ds.get("border_color", _BORDER[i % len(_BORDER)])
        ds_js.append(
            f'{{label:"{ds.get("label","")}",data:{ds.get("data",[])}'
            f',backgroundColor:"{color}",borderColor:"{border}"'
            f',borderWidth:1}}'
        )

    ds_str = ",".join(ds_js)
    labels_str = str(labels).replace("'", '"')

    if not labels and not datasets:
        tool = p.get("data_tool", "")
        hx = (
            f' hx-get="/api/tools/{tool}" hx-trigger="load"'
            f' hx-swap="innerHTML"' if tool else ""
        )
        return (
            f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
            f'<div class="card-body">'
            f'<h3 class="card-title text-sm">{title}</h3>'
            f'<div class="{height} flex items-center justify-center'
            f' bg-base-200/50 rounded-lg border border-dashed'
            f' border-base-300"{hx}>'
            f'<span class="loading loading-spinner loading-md'
            f' text-primary"></span></div></div></div>'
        )

    chart_type = "line" if ct == "area" else ct
    fill = "true" if ct == "area" else "false"

    return (
        f'<div class="card bg-base-100 shadow-sm" id="comp-{c.id}">'
        f'<div class="card-body">'
        f'<h3 class="card-title text-sm">{title}</h3>'
        f'<div class="{height}"><canvas id="{canvas_id}"></canvas></div>'
        f'</div></div>'
        f'<script>(function(){{'
        f'new Chart(document.getElementById("{canvas_id}"),{{'
        f'type:"{chart_type}",'
        f'data:{{labels:{labels_str},datasets:[{ds_str}]}},'
        f'options:{{responsive:true,maintainAspectRatio:false,'
        f'fill:{fill},'
        f'plugins:{{legend:{{display:{str(len(datasets)>1).lower()}}}}},'
        f'scales:{{y:{{beginAtZero:true}}}}'
        f'}}}});}})()</script>'
    )
