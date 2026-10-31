"""Tests for ``ui_paint_uiresource`` (bd:python-factory-v2dko).

Carrier #5 producer (mcp-ui UIResource envelope) — sibling of
``paint_chat.py`` (carrier #1) but emits the spec-nested
``{type:"resource", resource:{uri, mimeType, text|blob}}`` shape
instead of A2UI ``{components, name}``.

EPIC bd:python-factory-lo1g9. Wire shape verification (FastMCP wraps
as MCP ``EmbeddedResource`` content block) lives in the byte-trace
sibling at ``test_paint_uiresource_byte_trace.py``.
"""

from __future__ import annotations

from typing import Any

from hypothesis import given, settings, strategies as st

from factory.ui.mcp.paint_uiresource import register


class _Harness:
    def __init__(self) -> None:
        self.tools: dict[str, Any] = {}

    def tool(self):
        def deco(fn):
            self.tools[fn.__name__] = fn
            return fn
        return deco


def _make_tool() -> Any:
    mcp = _Harness()
    register(mcp, get_runtime=lambda: None)
    tool = mcp.tools["ui_paint_uiresource"]

    def invoke(**kwargs: Any) -> dict[str, Any]:
        result = tool(**kwargs)
        return {"error": result.error} if not result.ok else result.data.model_dump(by_alias=True)

    return invoke


# --- Happy paths ----------------------------------------------------------


def test_remote_dom_default_mime_and_envelope():
    """Default ``remote_dom`` mode emits the RemoteDOM JS mime."""
    tool = _make_tool()
    result = tool(body="root.appendChild(document.createElement('button'));")
    assert "error" not in result
    assert result["type"] == "resource"
    assert result["resource"]["mimeType"] == (
        "application/vnd.mcp-ui.remote-dom+javascript")
    assert result["resource"]["text"] == (
        "root.appendChild(document.createElement('button'));")
    assert result["resource"]["uri"].startswith("ui://factory/")


def test_inline_html_mime():
    """``inline_html`` mode → ``text/html;profile=mcp-app`` mime."""
    result = _make_tool()(body="<h1>Hi</h1>", mode="inline_html")
    assert "error" not in result
    assert result["resource"]["mimeType"] == "text/html;profile=mcp-app"
    assert result["resource"]["text"] == "<h1>Hi</h1>"


def test_external_url_mime():
    """``external_url`` mode → ``text/uri-list`` mime per mcp-ui spec."""
    result = _make_tool()(
        body="https://example.com/widget", mode="external_url")
    assert "error" not in result
    assert result["resource"]["mimeType"] == "text/uri-list"
    assert result["resource"]["text"] == "https://example.com/widget"


def test_uri_uses_custom_suffix_when_provided():
    """Custom ``uri_suffix`` flows through verbatim."""
    result = _make_tool()(
        body="<p>x</p>", mode="inline_html", uri_suffix="my-card")
    assert result["resource"]["uri"] == "ui://factory/my-card"


def test_uri_default_is_uuid4():
    """Default URI suffix is a fresh UUID4 — different across calls."""
    tool = _make_tool()
    r1 = tool(body="a", mode="inline_html")
    r2 = tool(body="b", mode="inline_html")
    assert r1["resource"]["uri"] != r2["resource"]["uri"]
    # Both follow the canonical ``ui://factory/`` prefix.
    assert r1["resource"]["uri"].startswith("ui://factory/")
    assert r2["resource"]["uri"].startswith("ui://factory/")


def test_optional_name_metadata():
    """Optional ``name`` flows into ``_factory_name`` metadata."""
    result = _make_tool()(
        body="<p>x</p>", mode="inline_html", name="My Widget")
    assert result["_factory_name"] == "My Widget"


def test_default_name_metadata_is_uiresource():
    result = _make_tool()(body="x", mode="inline_html")
    assert result["_factory_name"] == "UIResource"


def test_factory_mode_metadata_recorded():
    """Mode is echoed into ``_factory_mode`` for downstream consumers."""
    for mode in ("inline_html", "external_url", "remote_dom"):
        body = "https://x" if mode == "external_url" else "x"
        result = _make_tool()(body=body, mode=mode)
        assert result["_factory_mode"] == mode


# --- Error paths (never raise) --------------------------------------------


def test_invalid_mode_returns_error_envelope():
    result = _make_tool()(
        body="<p>x</p>", mode="not-a-mode")  # type: ignore[arg-type]
    assert "error" in result
    assert "Invalid mode" in result["error"]


def test_empty_body_returns_error_envelope():
    result = _make_tool()(body="", mode="inline_html")
    assert "error" in result
    assert "must not be empty" in result["error"]


def test_non_string_body_returns_error_envelope():
    result = _make_tool()(body=123, mode="inline_html")  # type: ignore[arg-type]
    assert "error" in result
    assert "must be a string" in result["error"]


def test_none_body_returns_error_envelope():
    result = _make_tool()(body=None, mode="inline_html")  # type: ignore[arg-type]
    assert "error" in result
    assert "must be a string" in result["error"]


# --- Hypothesis property test ---------------------------------------------


_modes = st.sampled_from(["inline_html", "external_url", "remote_dom"])
_body = st.text(min_size=1, max_size=50)
_suffix = st.one_of(
    st.none(),
    st.text(alphabet="abcdefghijklmnopqrstuvwxyz0123456789-",
            min_size=1, max_size=20),
)


@given(body=_body, mode=_modes, name=st.one_of(st.none(), st.text(min_size=1, max_size=15)),
       suffix=_suffix)
@settings(max_examples=40, deadline=None)
def test_property_tool_always_returns_dict_with_invariants(
        body: str, mode: str, name, suffix):
    """Tool always returns dict; success → carrier #5 wire shape holds."""
    result = _make_tool()(body=body, mode=mode, name=name, uri_suffix=suffix)
    assert isinstance(result, dict)
    if "error" in result:
        # Only error path triggered by invalid inputs we don't generate;
        # generated bodies are always non-empty strings + valid modes.
        assert isinstance(result["error"], str)
        return
    # Wire-shape invariants — what FastMCP / EmbeddedResource consumers see.
    assert result["type"] == "resource"
    assert isinstance(result["resource"], dict)
    assert result["resource"]["uri"].startswith("ui://factory/")
    assert isinstance(result["resource"]["mimeType"], str)
    assert result["resource"]["text"] == body
    # Sentinel keys MUST NOT leak across carriers.
    assert "_a2ui_canvas" not in result
    assert "components" not in result
