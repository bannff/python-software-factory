"""Tests for LazyBrickLoader eager and deferred loading.

Verifies both loading modes:
- EAGER_LOAD=1: set_available() imports all bricks, accurate tool counts
- EAGER_LOAD unset (default): set_available() defers loading, tools_count=-1
"""

from __future__ import annotations

import os
from types import SimpleNamespace
from unittest.mock import patch

from factory.mcp_server.runtime.lazy_loader import LazyBrickLoader
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from .typed_tool_fixtures import add_empty_tool


def _mock_brick_mcp(tool_count: int = 3) -> ToolCatalog:
    """Create a neutral catalog with admitted strict typed tools."""
    catalog = ToolCatalog("lazy-loader-test")
    for index in range(tool_count):
        add_empty_tool(catalog, f"tool_{index}")
    return catalog


def _module(catalog: ToolCatalog) -> SimpleNamespace:
    return SimpleNamespace(create_tool_catalog=lambda: catalog)


class TestEagerLoading:
    """With EAGER_LOAD=1, set_available() imports all bricks immediately."""

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_all_bricks_loaded(self, mock_import):
        mock_mcp = _mock_brick_mcp(tool_count=2)
        mock_import.return_value = _module(mock_mcp)

        loader = LazyBrickLoader()
        loader.set_available(["alpha", "beta"])

        assert "alpha" in loader._cache
        assert "beta" in loader._cache

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_tools_count_accurate(self, mock_import):
        mock_mcp = _mock_brick_mcp(tool_count=4)
        mock_import.return_value = _module(mock_mcp)

        loader = LazyBrickLoader()
        loader.set_available(["brick_a", "brick_b"])

        for name in ["brick_a", "brick_b"]:
            reg = loader.registrations[name]
            assert reg.tools_count == 4
            assert reg.healthy is True

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_failed_brick_marked_unhealthy(self, mock_import):
        mock_import.side_effect = ImportError("no such module")

        loader = LazyBrickLoader()
        loader.set_available(["missing_brick"])

        reg = loader.registrations["missing_brick"]
        assert reg.healthy is False
        assert reg.tools_count == 0
        assert reg.error is not None

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_mixed_success_and_failure(self, mock_import):
        mock_mcp = _mock_brick_mcp(tool_count=5)
        good_module = _module(mock_mcp)

        def side_effect(name):
            if "bad" in name:
                raise ImportError(f"Cannot import {name}")
            return good_module

        mock_import.side_effect = side_effect

        loader = LazyBrickLoader()
        loader.set_available(["good_brick", "bad_brick"])

        assert loader.registrations["good_brick"].healthy is True
        assert loader.registrations["good_brick"].tools_count == 5
        assert loader.registrations["bad_brick"].healthy is False
        assert loader.registrations["bad_brick"].tools_count == 0

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_ensure_loaded_not_called_twice(self, mock_import):
        mock_mcp = _mock_brick_mcp(tool_count=1)
        mock_import.return_value = _module(mock_mcp)

        loader = LazyBrickLoader()
        loader.set_available(["brick_x"])
        assert mock_import.call_count == 1

        loader.ensure_loaded("brick_x")
        assert mock_import.call_count == 1


class TestDeferredLoading:
    """Without EAGER_LOAD, set_available() defers — no imports at init."""

    @patch.dict(os.environ, {}, clear=False)
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_no_imports_at_set_available(self, mock_import):
        os.environ.pop("EAGER_LOAD", None)
        loader = LazyBrickLoader()
        loader.set_available(["alpha", "beta"])

        assert mock_import.call_count == 0
        assert loader._cache == {}

    @patch.dict(os.environ, {}, clear=False)
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_tools_count_minus_one_before_load(self, mock_import):
        os.environ.pop("EAGER_LOAD", None)
        loader = LazyBrickLoader()
        loader.set_available(["brick_a"])

        reg = loader.registrations["brick_a"]
        assert reg.tools_count == -1
        assert reg.healthy is True

    @patch.dict(os.environ, {}, clear=False)
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_ensure_loaded_triggers_import(self, mock_import):
        os.environ.pop("EAGER_LOAD", None)
        mock_mcp = _mock_brick_mcp(tool_count=3)
        mock_import.return_value = _module(mock_mcp)

        loader = LazyBrickLoader()
        loader.set_available(["brick_a"])
        assert mock_import.call_count == 0

        result = loader.ensure_loaded("brick_a")
        assert result is mock_mcp
        assert mock_import.call_count == 1
        assert loader.registrations["brick_a"].tools_count == 3


class TestSharedBehavior:
    """Behavior that works the same regardless of EAGER_LOAD."""

    def test_empty_set_available(self):
        loader = LazyBrickLoader()
        loader.set_available([])
        assert loader.registrations == {}
        assert loader.available_bricks == []

    @patch.dict(os.environ, {"EAGER_LOAD": "1"})
    @patch("factory.mcp_server.runtime.lazy_loader.importlib.import_module")
    def test_available_bricks_property(self, mock_import):
        mock_mcp = _mock_brick_mcp(tool_count=1)
        mock_import.return_value = _module(mock_mcp)

        loader = LazyBrickLoader()
        loader.set_available(["a", "b", "c"])
        assert loader.available_bricks == ["a", "b", "c"]
