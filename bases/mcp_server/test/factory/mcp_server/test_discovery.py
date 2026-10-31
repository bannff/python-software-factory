"""Tests for brick discovery.

Tests the BrickDiscovery class which reads BRICKS_INDEX.yaml
to discover available MCP-enabled bricks in the workspace.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import mock_open, patch

import pytest

from factory.mcp_server import BrickDiscovery, BrickInfo


class TestBrickInfo:
    """Tests for BrickInfo dataclass."""

    def test_brick_info_creation(self):
        """BrickInfo should store all required fields."""
        info = BrickInfo(
            name="test",
            namespace="factory.test",
            brick_type="component",
            mcp_enabled=True,
            description="Test brick",
            features=["feature1"],
        )
        assert info.name == "test"
        assert info.namespace == "factory.test"
        assert info.mcp_enabled is True

    def test_brick_info_defaults(self):
        """BrickInfo should have sensible defaults."""
        info = BrickInfo(name="test", namespace="ns", brick_type="component", mcp_enabled=False)
        assert info.description == ""
        assert info.features is None


class TestBrickDiscovery:
    """Tests for BrickDiscovery class."""

    def test_discover_bricks_returns_list(self, tmp_path: Path):
        """Discovery should return a list of BrickInfo objects."""
        index_content = """
bricks:
  components:
    - name: kb
      namespace: factory.kb
      mcp_enabled: true
  bases: []
"""
        index_file = tmp_path / "BRICKS_INDEX.yaml"
        index_file.write_text(index_content)

        discovery = BrickDiscovery(workspace_root=tmp_path)
        bricks = discovery.discover_bricks()

        assert isinstance(bricks, list)
        assert len(bricks) == 1
        assert bricks[0].name == "kb"

    def test_discover_filters_mcp_enabled(self, tmp_path: Path):
        """Only mcp_enabled bricks should be discovered when mcp_only=True."""
        index_content = """
bricks:
  components:
    - name: enabled
      namespace: factory.enabled
      mcp_enabled: true
    - name: disabled
      namespace: factory.disabled
      mcp_enabled: false
  bases: []
"""
        index_file = tmp_path / "BRICKS_INDEX.yaml"
        index_file.write_text(index_content)

        discovery = BrickDiscovery(workspace_root=tmp_path)

        mcp_bricks = discovery.discover_bricks(mcp_only=True)
        assert len(mcp_bricks) == 1
        assert mcp_bricks[0].name == "enabled"

        all_bricks = discovery.discover_bricks(mcp_only=False)
        assert len(all_bricks) == 2

    def test_discover_handles_missing_index(self, tmp_path: Path):
        """Should handle missing BRICKS_INDEX gracefully."""
        discovery = BrickDiscovery(workspace_root=tmp_path)
        bricks = discovery.discover_bricks()

        assert isinstance(bricks, list)
        assert len(bricks) == 0

    def test_get_brick_names(self, tmp_path: Path):
        """get_brick_names should return list of names."""
        index_content = """
bricks:
  components:
    - name: auth
      namespace: factory.auth
      mcp_enabled: true
  bases:
    - name: mcp_server
      namespace: factory.mcp_server
      mcp_enabled: true
"""
        index_file = tmp_path / "BRICKS_INDEX.yaml"
        index_file.write_text(index_content)

        discovery = BrickDiscovery(workspace_root=tmp_path)
        names = discovery.get_brick_names()

        assert "auth" in names
        assert "mcp_server" in names


    def test_get_brick_names_filtered_by_pyproject(self, tmp_path: Path):
        """When pyproject.toml has [tool.polylith.bricks], only those bricks returned."""
        index_content = """
bricks:
  components:
    - name: agent
      namespace: factory.agent
      mcp_enabled: true
    - name: legacy_example
      namespace: factory.legacy_example
      mcp_enabled: true
    - name: test
      namespace: factory.test
      mcp_enabled: true
  bases: []
"""
        (tmp_path / "BRICKS_INDEX.yaml").write_text(index_content)

        # pyproject.toml only declares agent — legacy_example and test excluded
        pyproject_content = """
[tool.polylith.bricks]
"../../components/agent/src/factory/agent" = "factory/agent"
"""
        (tmp_path / "pyproject.toml").write_text(pyproject_content)

        discovery = BrickDiscovery(workspace_root=tmp_path)
        names = discovery.get_brick_names()

        assert names == ["agent"]
        assert "legacy_example" not in names
        assert "test" not in names

    def test_get_brick_names_falls_back_to_index_without_pyproject(self, tmp_path: Path):
        """Without pyproject.toml, all bricks from BRICKS_INDEX are returned."""
        index_content = """
bricks:
  components:
    - name: agent
      namespace: factory.agent
      mcp_enabled: true
    - name: legacy_example
      namespace: factory.legacy_example
      mcp_enabled: true
  bases: []
"""
        (tmp_path / "BRICKS_INDEX.yaml").write_text(index_content)
        # No pyproject.toml

        discovery = BrickDiscovery(workspace_root=tmp_path)
        names = discovery.get_brick_names()

        assert "agent" in names
        assert "legacy_example" in names

    def test_get_brick_names_pyproject_without_polylith_section(self, tmp_path: Path):
        """pyproject.toml without [tool.polylith.bricks] falls back to BRICKS_INDEX."""
        index_content = """
bricks:
  components:
    - name: agent
      namespace: factory.agent
      mcp_enabled: true
  bases: []
"""
        (tmp_path / "BRICKS_INDEX.yaml").write_text(index_content)
        (tmp_path / "pyproject.toml").write_text("[project]\nname = 'test'\n")

        discovery = BrickDiscovery(workspace_root=tmp_path)
        names = discovery.get_brick_names()

        assert "agent" in names
