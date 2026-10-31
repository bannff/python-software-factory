"""Flet adapter — renders views as real ft.Control instances.

Cross-platform UI (web, desktop, mobile) via Flet + Material 3.
"""

from __future__ import annotations

from typing import Any

import flet as ft

from ..models import ComponentType, UIComponent, UIView
from .base import RenderAdapter, RenderResult
from . import flet_renderers as fr
from .flet_renderers_page import render_page, render_composed_page
from .flet_renderers_ext import (
    render_hero, render_tabs, render_breadcrumbs,
    render_modal, render_toast,
)
from .flet_renderers_interactive import (
    render_code_block, render_timeline, render_stat_grid,
    render_tree_view, render_live_feed,
)
from .flet_renderers_action_pane import render_action_pane
from .flet_renderers_chart import render_chart_native
from .flet_renderers_graph import render_graph_viewer


class FletAdapter(RenderAdapter):
    """Renders views as real ft.Control trees."""

    def __init__(self, theme: str = "light", use_material3: bool = True):
        self._theme = theme
        self._use_material3 = use_material3

    @property
    def adapter_type(self) -> str:
        return "flet"

    @property
    def content_type(self) -> str:
        return "application/x-flet-control"

    def render_view(self, view: UIView) -> RenderResult:
        """Render view as ft.Control tree."""
        controls = [self._render_component(c) for c in view.components]
        layout_type = view.layout.get("type", "column")
        root = fr.make_layout_control(layout_type, controls)

        return RenderResult(
            adapter_type=self.adapter_type,
            content=root,
            content_type=self.content_type,
            metadata={
                "theme": self._theme,
                "component_count": len(view.components),
                "view_id": view.id,
            },
        )

    def render_component(self, component: UIComponent) -> RenderResult:
        """Render single component as ft.Control."""
        ctrl = self._render_component(component)
        return RenderResult(
            adapter_type=self.adapter_type,
            content=ctrl,
            content_type=self.content_type,
        )

    def supports_streaming(self) -> bool:
        return True

    def _render_component(self, c: UIComponent) -> ft.Control:
        """Dispatch to component-specific renderer."""
        # Components needing recursive render_child
        match c.component_type:
            case ComponentType.CARD:
                return fr.render_card(c, self._render_component)
            case ComponentType.PAGE:
                return render_page(c, self._render_component)
            case ComponentType.COMPOSED_PAGE:
                return render_composed_page(c, self._render_component)
            case ComponentType.TABS:
                return render_tabs(c, self._render_component)

        # Simple renderers (no children)
        renderers = {
            ComponentType.TEXT: fr.render_text,
            ComponentType.BUTTON: fr.render_button,
            ComponentType.TABLE: fr.render_table,
            ComponentType.METRIC: fr.render_metric,
            ComponentType.ALERT: fr.render_alert,
            ComponentType.PROGRESS: fr.render_progress,
            ComponentType.FORM: fr.render_form,
            ComponentType.LIST: fr.render_list,
            ComponentType.CHART: render_chart_native,
            ComponentType.IMAGE: fr.render_image,
            ComponentType.HERO: render_hero,
            ComponentType.BREADCRUMBS: render_breadcrumbs,
            ComponentType.MODAL: render_modal,
            ComponentType.TOAST: render_toast,
            ComponentType.ACTION_PANE: render_action_pane,
            ComponentType.CODE_BLOCK: render_code_block,
            ComponentType.TIMELINE: render_timeline,
            ComponentType.STAT_GRID: render_stat_grid,
            ComponentType.TREE_VIEW: render_tree_view,
            ComponentType.LIVE_FEED: render_live_feed,
            ComponentType.GRAPH_VIEWER: render_graph_viewer,
        }
        renderer = renderers.get(c.component_type, fr.render_custom)
        return renderer(c)
