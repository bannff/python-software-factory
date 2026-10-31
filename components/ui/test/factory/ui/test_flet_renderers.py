"""Tests for Flet renderers — palette, form, and complex control modules."""
from __future__ import annotations

import re
import pytest
ft = pytest.importorskip("flet", reason="Flet renderer tests require the optional UI backend")
from factory.ui.runtime.models import UIComponent, ComponentType
from factory.ui.runtime.adapters import flet_palette as P
from factory.ui.runtime.adapters.flet_renderers_form import render_form
from factory.ui.runtime.adapters.flet_renderers_complex import (
    render_table, render_metric, render_alert,
    render_list, render_chart, render_card,
)

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _comp(ctype: ComponentType, props=None, children=None) -> UIComponent:
    return UIComponent(id="t", component_type=ctype,
                       props=props or {}, children=children or [])


def _identity(c: UIComponent) -> ft.Control:
    return ft.Text(c.id)


# ── Palette ──────────────────────────────────────────────────────────

_PALETTE_NAMES = ("PRIMARY", "SECONDARY", "TERTIARY", "SURFACE_VARIANT",
                  "OUTLINE", "SUCCESS", "ERROR")


class TestPalette:
    def test_all_constants_are_hex(self):
        for name in _PALETTE_NAMES:
            assert _HEX_RE.match(getattr(P, name)), f"{name} not valid hex"

    def test_constants_are_distinct(self):
        vals = [getattr(P, n) for n in _PALETTE_NAMES]
        assert len(vals) == len(set(vals))


# ── Form renderer ────────────────────────────────────────────────────

class TestRenderForm:
    def test_basic_form_returns_container(self):
        assert isinstance(render_form(_comp(ComponentType.FORM, {"fields": []})), ft.Container)

    def test_submit_button_present(self):
        col = render_form(_comp(ComponentType.FORM, {"fields": []})).content
        assert isinstance(col.controls[-1], ft.Button)

    def test_text_field(self):
        c = _comp(ComponentType.FORM, {"fields": [{"name": "q", "label": "Q", "type": "text"}]})
        assert isinstance(render_form(c).content.controls[0], ft.TextField)

    def test_password_field(self):
        c = _comp(ComponentType.FORM, {"fields": [{"name": "p", "type": "password"}]})
        f = render_form(c).content.controls[0]
        assert isinstance(f, ft.TextField) and f.password is True

    def test_textarea_field(self):
        c = _comp(ComponentType.FORM, {"fields": [{"name": "b", "type": "textarea"}]})
        f = render_form(c).content.controls[0]
        assert f.multiline is True and f.min_lines == 3

    def test_select_field_dict_options(self):
        c = _comp(ComponentType.FORM, {
            "fields": [{"name": "m", "type": "select",
                         "options": [{"value": "a", "label": "A"}]}],
        })
        assert isinstance(render_form(c).content.controls[0], ft.Dropdown)

    def test_select_field_string_options(self):
        c = _comp(ComponentType.FORM, {
            "fields": [{"name": "x", "type": "select", "options": ["one"]}],
        })
        assert render_form(c).content.controls[0].options[0].key == "one"

    def test_range_field(self):
        c = _comp(ComponentType.FORM, {
            "fields": [{"name": "n", "type": "range", "min": 1, "max": 50, "value": 10}],
        })
        s = render_form(c).content.controls[0].controls[1]
        assert isinstance(s, ft.Slider) and s.min == 1 and s.max == 50

    def test_empty_fields_only_submit(self):
        assert len(render_form(_comp(ComponentType.FORM, {"fields": []})).content.controls) == 1

    def test_tooltip_propagated(self):
        c = _comp(ComponentType.FORM, {
            "fields": [{"name": "q", "type": "text", "tooltip": "help"}],
        })
        assert render_form(c).content.controls[0].tooltip == "help"


# ── Complex renderers ────────────────────────────────────────────────

class TestRenderTable:
    def test_returns_container(self):
        c = _comp(ComponentType.TABLE, {"columns": ["A"], "rows": [["1"]]})
        assert isinstance(render_table(c), ft.Container)

    def test_column_and_row_counts(self):
        c = _comp(ComponentType.TABLE, {
            "columns": ["X", "Y"], "rows": [["1", "2"], ["3", "4"]],
        })
        dt = render_table(c).content
        assert len(dt.columns) == 2 and len(dt.rows) == 2

    def test_empty_table(self):
        c = _comp(ComponentType.TABLE, {"columns": [], "rows": []})
        dt = render_table(c).content
        assert len(dt.columns) == 0 and len(dt.rows) == 0

    def test_dict_columns(self):
        c = _comp(ComponentType.TABLE, {
            "columns": [{"key": "id", "label": "ID"}], "rows": [],
        })
        assert len(render_table(c).content.columns) == 1

    def test_data_key_alias(self):
        c = _comp(ComponentType.TABLE, {"columns": ["A"], "data": [["v"]]})
        assert len(render_table(c).content.rows) == 1


class TestRenderMetric:
    def test_returns_container(self):
        c = _comp(ComponentType.METRIC, {"label": "Users", "value": 42})
        assert isinstance(render_metric(c), ft.Container)

    def test_positive_change(self):
        c = _comp(ComponentType.METRIC, {"value": 1, "change": "+5%"})
        assert render_metric(c).content.controls[-1].color == "#66BB6A"

    def test_negative_change(self):
        c = _comp(ComponentType.METRIC, {"value": 1, "change": "-3%"})
        assert render_metric(c).content.controls[-1].color == ft.Colors.ERROR

    def test_no_change_omits_text(self):
        c = _comp(ComponentType.METRIC, {"value": 1})
        assert len(render_metric(c).content.controls) == 2


class TestRenderAlert:
    def test_all_severities(self):
        for sev in ("info", "success", "warning", "error", "alien"):
            c = _comp(ComponentType.ALERT, {"message": "m", "severity": sev})
            assert isinstance(render_alert(c), ft.Container)

    def test_text_prop_fallback(self):
        c = _comp(ComponentType.ALERT, {"text": "fallback"})
        assert render_alert(c).content.controls[1].value == "fallback"


class TestRenderListAndChart:
    def test_list_returns_listview(self):
        c = _comp(ComponentType.LIST, {"items": ["a", "b"]})
        assert isinstance(render_list(c), ft.ListView)

    def test_list_dict_items(self):
        c = _comp(ComponentType.LIST, {
            "items": [{"title": "T", "subtitle": "S"}],
        })
        assert isinstance(render_list(c).controls[0], ft.ListTile)

    def test_list_empty(self):
        assert len(render_list(_comp(ComponentType.LIST, {"items": []})).controls) == 0

    def test_chart_types(self):
        for ct in ("line", "bar", "pie", "area", "scatter", "radar"):
            c = _comp(ComponentType.CHART, {"chart_type": ct})
            assert isinstance(render_chart(c), ft.Container)

    def test_chart_custom_height(self):
        c = _comp(ComponentType.CHART, {"height": 400})
        assert render_chart(c).height == 400

    def test_chart_default_height(self):
        assert render_chart(_comp(ComponentType.CHART, {})).height == 200


class TestRenderCard:
    def test_returns_container(self):
        c = _comp(ComponentType.CARD, {"title": "C"})
        assert isinstance(render_card(c, _identity), ft.Container)

    def test_title_present(self):
        c = render_card(_comp(ComponentType.CARD, {"title": "Hi"}), _identity)
        assert c.content.controls[0].value == "Hi"

    def test_no_title_no_children(self):
        c = render_card(_comp(ComponentType.CARD, {}), _identity)
        assert len(c.content.controls) == 0

    def test_children_rendered(self):
        child = _comp(ComponentType.TEXT, {"content": "hi"})
        c = _comp(ComponentType.CARD, {"title": "C"}, children=[child])
        assert len(render_card(c, _identity).content.controls) == 2
