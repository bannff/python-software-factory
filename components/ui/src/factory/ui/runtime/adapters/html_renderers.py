"""HTML renderers for MCP-UI components.

Provides HTML rendering functions for each component type.
"""

import json
from typing import Any

from ..models import UIComponent, UIView


def styles_to_css(styles: dict[str, str]) -> str:
    """Convert styles dict to CSS string."""
    return "; ".join(f"{k}: {v}" for k, v in styles.items())


def layout_to_css(layout: dict[str, Any]) -> str:
    """Convert layout dict to CSS string."""
    css_parts = []
    if layout.get("type") == "grid":
        cols = layout.get("columns", 1)
        css_parts.append(
            f"display: grid; grid-template-columns: repeat({cols}, 1fr); gap: 1rem"
        )
    elif layout.get("type") == "flex":
        direction = layout.get("direction", "row")
        css_parts.append(f"display: flex; flex-direction: {direction}; gap: 1rem")
    return "; ".join(css_parts)


def json_encode(data: Any) -> str:
    """JSON encode data for embedding in HTML."""
    return json.dumps(data)


def render_text(c: UIComponent) -> str:
    """Render text component."""
    variant = c.props.get("variant", "body")
    content = c.props.get("content", "")
    tag_map = {"h1": "h1", "h2": "h2", "h3": "h3", "body": "p", "caption": "span"}
    tag = tag_map.get(variant, "p")
    style = styles_to_css(c.styles)
    return (
        f'<{tag} class="mcp-ui-text mcp-ui-text--{variant}" style="{style}">{content}</{tag}>'
    )


def render_chart(c: UIComponent) -> str:
    """Render chart component placeholder."""
    chart_type = c.props.get("chart_type", "line")
    title = c.props.get("title", "")
    data = c.props.get("data", [])
    return f"""<div class="mcp-ui-chart" data-chart-type="{chart_type}" \
data-component-id="{c.id}">
  <div class="chart-title">{title}</div>
  <div class="chart-placeholder">[{chart_type.upper()} CHART - {len(data)} data points]</div>
  <script type="application/json">{json_encode(data)}</script>
</div>"""


def render_table(c: UIComponent) -> str:
    """Render table component."""
    columns, rows = c.props.get("columns", []), c.props.get("rows", [])
    header = "<tr>" + "".join(f"<th>{col.get('label', col.get('key', ''))}" for col in columns) + "</tr>"
    body = "\n".join("<tr>" + "".join(f"<td>{row.get(col.get('key', ''), '')}" for col in columns) + "</tr>" for row in rows)
    return f'<table class="mcp-ui-table" data-component-id="{c.id}"><thead>{header}</thead><tbody>{body}</tbody></table>'


def render_metric(c: UIComponent) -> str:
    """Render metric component."""
    label, value, unit = c.props.get("label", ""), c.props.get("value", ""), c.props.get("unit", "")
    trend, trend_value = c.props.get("trend", ""), c.props.get("trend_value", "")
    trend_html = ""
    if trend:
        icon = {"up": "↑", "down": "↓", "flat": "→"}.get(trend, "")
        trend_html = f'<span class="metric-trend trend--{trend}">{icon} {trend_value}</span>'
    return f'<div class="mcp-ui-metric" data-component-id="{c.id}"><div class="metric-label">{label}</div><div class="metric-value">{value}<span class="metric-unit">{unit}</span></div>{trend_html}</div>'


def render_card(c: UIComponent, component_to_html_fn) -> str:
    """Render card component with children."""
    title, subtitle, content = c.props.get("title", ""), c.props.get("subtitle", ""), c.props.get("content", "")
    children_html = "\n".join(component_to_html_fn(child) for child in c.children)
    return f'<div class="mcp-ui-card" data-component-id="{c.id}"><div class="card-header"><div class="card-title">{title}</div><div class="card-subtitle">{subtitle}</div></div><div class="card-content">{content}{children_html}</div></div>'


def render_alert(c: UIComponent) -> str:
    """Render alert component."""
    message = c.props.get("message", "")
    severity = c.props.get("severity", "info")
    css_class = f"mcp-ui-alert mcp-ui-alert--{severity}"
    return f'<div class="{css_class}" data-component-id="{c.id}">{message}</div>'


def render_progress(c: UIComponent) -> str:
    """Render progress component."""
    value, label = c.props.get("value", 0), c.props.get("label", "")
    variant = c.props.get("variant", "linear")
    if variant == "circular":
        return (f'<div class="mcp-ui-progress mcp-ui-progress--circular"'
                f' data-component-id="{c.id}" role="progressbar"'
                f' aria-valuenow="{value}" aria-valuemin="0" aria-valuemax="100">'
                f'<span class="progress-label">{label} {value}%</span></div>')
    return (f'<div class="mcp-ui-progress mcp-ui-progress--linear"'
            f' data-component-id="{c.id}">'
            f'<div class="progress-label">{label}</div>'
            f'<div class="progress-bar">'
            f'<div class="progress-fill" style="width: {value}%"></div></div>'
            f'<div class="progress-value">{value}%</div></div>')


def render_form(c: UIComponent) -> str:
    """Render form component."""
    fields, submit_label = c.props.get("fields", []), c.props.get("submit_label", "Submit")
    fields_html = "\n".join(
        f'<div class="form-field"><label for="{f.get("name", "")}">{f.get("label", f.get("name", ""))}</label>'
        f'<input type="{f.get("type", "text")}" name="{f.get("name", "")}" id="{f.get("name", "")}" /></div>'
        for f in fields
    )
    return f'<form class="mcp-ui-form" data-component-id="{c.id}">{fields_html}<button type="submit">{submit_label}</button></form>'


def render_button(c: UIComponent) -> str:
    """Render button component."""
    label = c.props.get("label", "Button")
    variant = c.props.get("variant", "primary")
    css_class = f"mcp-ui-button mcp-ui-button--{variant}"
    return f'<button class="{css_class}" data-component-id="{c.id}">{label}</button>'


def render_image(c: UIComponent) -> str:
    """Render image component."""
    src = c.props.get("src", "")
    alt = c.props.get("alt", "")
    return f'<img class="mcp-ui-image" src="{src}" alt="{alt}" data-component-id="{c.id}" />'


def render_list(c: UIComponent) -> str:
    """Render list component."""
    items = c.props.get("items", [])
    ordered = c.props.get("ordered", False)
    tag = "ol" if ordered else "ul"
    items_html = "\n".join(f"<li>{item}</li>" for item in items)
    return f'<{tag} class="mcp-ui-list" data-component-id="{c.id}">{items_html}</{tag}>'


def render_custom(c: UIComponent) -> str:
    """Render custom component as JSON."""
    data_type = c.component_type.value
    json_props = json_encode(c.props)
    return (
        f'<div class="mcp-ui-custom" data-component-id="{c.id}" '
        f'data-type="{data_type}">{json_props}</div>'
    )


def generate_view_styles(view: UIView) -> str:
    """Generate CSS styles for a view."""
    return """.mcp-ui-view{font-family:system-ui,sans-serif;padding:1rem}.mcp-ui-metric{text-align:center;padding:1rem}.mcp-ui-metric .metric-value{font-size:2rem;font-weight:bold}.mcp-ui-metric .metric-label{color:#666}.mcp-ui-metric .trend--up{color:#22c55e}.mcp-ui-metric .trend--down{color:#ef4444}.mcp-ui-table{width:100%;border-collapse:collapse}.mcp-ui-table th,.mcp-ui-table td{padding:.5rem;border:1px solid #ddd;text-align:left}.mcp-ui-table th{background:#f5f5f5}.mcp-ui-card{border:1px solid #ddd;border-radius:8px;padding:1rem}.mcp-ui-alert{padding:1rem;border-radius:4px}.mcp-ui-alert--info{background:#e0f2fe;color:#0369a1}.mcp-ui-alert--success{background:#dcfce7;color:#166534}.mcp-ui-alert--warning{background:#fef3c7;color:#92400e}.mcp-ui-alert--error{background:#fee2e2;color:#991b1b}.mcp-ui-progress--linear .progress-bar{background:#e5e5e5;height:8px;border-radius:4px}.mcp-ui-progress--linear .progress-fill{background:#3b82f6;height:100%;border-radius:4px}"""
