"""Tests for Flet page renderer — 3-zone layout and composed page.

Verifies render_page produces a Column with hero, zone2, zone3 sections
and that children are routed to the correct zone based on props.
"""
from __future__ import annotations

import pytest
ft = pytest.importorskip("flet", reason="Flet renderer tests require the optional UI backend")

from factory.ui.runtime.models import UIComponent, ComponentType
from factory.ui.runtime.adapters.flet_renderers_page import (
    render_page, render_composed_page, _parse_gradient,
)


def _comp(ctype: ComponentType, props=None, children=None) -> UIComponent:
    return UIComponent(
        id="test", component_type=ctype,
        props=props or {}, children=children or [],
    )


def _identity(c: UIComponent) -> ft.Control:
    return ft.Text(c.id)


class TestRenderPage:
    def test_returns_column(self):
        c = _comp(ComponentType.PAGE, {"title": "T"})
        assert isinstance(render_page(c, _identity), ft.Column)

    def test_three_zones(self):
        c = _comp(ComponentType.PAGE, {"title": "T"})
        assert len(render_page(c, _identity).controls) == 3

    def test_hero_title_and_icon(self):
        c = _comp(ComponentType.PAGE, {"title": "Dash", "icon": "🔍"})
        hero = render_page(c, _identity).controls[0]
        assert isinstance(hero, ft.Container)
        texts = hero.content.controls
        assert texts[0].value == "🔍"
        assert texts[1].value == "Dash"

    def test_hero_subtitle(self):
        c = _comp(ComponentType.PAGE, {"title": "T", "subtitle": "Sub"})
        hero = render_page(c, _identity).controls[0]
        assert hero.content.controls[2].value == "Sub"

    def test_zone2_with_info_and_controls(self):
        info = _comp(ComponentType.METRIC, {"zone": "info", "value": 1})
        ctrl = _comp(ComponentType.FORM, {"zone": "controls"})
        c = _comp(ComponentType.PAGE, {"title": "T"}, children=[info, ctrl])
        zone2 = render_page(c, _identity).controls[1]
        assert isinstance(zone2, ft.ResponsiveRow)

    def test_zone2_empty_when_no_zoned_children(self):
        c = _comp(ComponentType.PAGE, {"title": "T"})
        zone2 = render_page(c, _identity).controls[1]
        assert isinstance(zone2, ft.Container)

    def test_zone3_output_children(self):
        tbl = _comp(ComponentType.TABLE, {"columns": []})
        c = _comp(ComponentType.PAGE, {"title": "T"}, children=[tbl])
        zone3 = render_page(c, _identity).controls[2]
        assert isinstance(zone3, ft.Column) and len(zone3.controls) == 1

    def test_zone3_empty(self):
        c = _comp(ComponentType.PAGE, {"title": "T"})
        zone3 = render_page(c, _identity).controls[2]
        assert isinstance(zone3, ft.Container)

    def test_two_column_output_layout(self):
        t1 = _comp(ComponentType.TABLE, {"columns": []})
        t2 = _comp(ComponentType.TABLE, {"columns": []})
        c = _comp(ComponentType.PAGE, {
            "title": "T", "output_layout": "two-column",
        }, children=[t1, t2])
        zone3 = render_page(c, _identity).controls[2]
        assert isinstance(zone3, ft.ResponsiveRow)

    def test_two_column_needs_two_items(self):
        """two-column with <2 items falls back to Column."""
        t1 = _comp(ComponentType.TABLE, {"columns": []})
        c = _comp(ComponentType.PAGE, {
            "title": "T", "output_layout": "two-column",
        }, children=[t1])
        zone3 = render_page(c, _identity).controls[2]
        assert isinstance(zone3, ft.Column)

    def test_gradient_known(self):
        c = _comp(ComponentType.PAGE, {
            "title": "T", "gradient": "from-red-500 to-orange-500",
        })
        hero = render_page(c, _identity).controls[0]
        assert hero.gradient is not None
        assert hero.gradient.colors == ["#FF5252", "#FF7043"]

    def test_gradient_unknown_defaults(self):
        colors = _parse_gradient("from-unknown-500 to-unknown-500")
        assert len(colors) == 2

    def test_scroll_enabled(self):
        c = _comp(ComponentType.PAGE, {"title": "T"})
        col = render_page(c, _identity)
        assert col.scroll == ft.ScrollMode.AUTO

    def test_mixed_zones(self):
        """Info, controls, and output children all route correctly."""
        info = _comp(ComponentType.METRIC, {"zone": "info"})
        ctrl = _comp(ComponentType.FORM, {"zone": "controls"})
        out = _comp(ComponentType.TABLE, {"columns": []})
        c = _comp(ComponentType.PAGE, {"title": "T"},
                  children=[info, ctrl, out])
        page = render_page(c, _identity)
        zone2 = page.controls[1]
        zone3 = page.controls[2]
        assert isinstance(zone2, ft.ResponsiveRow)
        assert isinstance(zone3, ft.Column) and len(zone3.controls) == 1


class TestRenderComposedPage:
    def test_returns_column(self):
        c = _comp(ComponentType.COMPOSED_PAGE, {})
        assert isinstance(render_composed_page(c, _identity), ft.Column)

    def test_children_rendered(self):
        child = _comp(ComponentType.TEXT, {"content": "hi"})
        c = _comp(ComponentType.COMPOSED_PAGE, {}, children=[child])
        assert len(render_composed_page(c, _identity).controls) == 1

    def test_empty_children(self):
        c = _comp(ComponentType.COMPOSED_PAGE, {})
        assert len(render_composed_page(c, _identity).controls) == 0

    def test_scroll_enabled(self):
        c = _comp(ComponentType.COMPOSED_PAGE, {})
        assert render_composed_page(c, _identity).scroll == ft.ScrollMode.AUTO
