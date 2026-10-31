"""Tests for adapter-aware infrastructure resolution and env generation.

Covers: read_adapter_selections, resolve_infra_from_bricks,
adapter-aware introspect_project, and render_env_example with adapters.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml

from factory.blueprint.runtime.deploy.introspect import (
    ProjectInfo,
    introspect_project,
    read_adapter_selections,
    resolve_infra_from_bricks,
)
from factory.blueprint.runtime.deploy.templates import render_env_example


@pytest.fixture
def workspace_root():
    path = Path(__file__).resolve()
    for parent in path.parents:
        if (parent / "workspace.toml").exists():
            return parent
    pytest.skip("Cannot find workspace root")


def _write_brick_yaml(ws: Path, brick: str, adapter_infra: dict) -> None:
    brick_dir = ws / "components" / brick
    brick_dir.mkdir(parents=True, exist_ok=True)
    (brick_dir / "BRICK.yaml").write_text(
        yaml.dump({"name": brick, "adapter_infra": adapter_infra}),
    )


class TestReadAdapterSelections:
    def test_single_adapter_line(self, tmp_path):
        (tmp_path / ".env").write_text("FACTORY_CACHE_ADAPTER=redis\n")
        assert read_adapter_selections(tmp_path) == {"cache": "redis"}

    def test_multiple_adapter_lines(self, tmp_path):
        (tmp_path / ".env").write_text(
            "FACTORY_CACHE_ADAPTER=redis\nFACTORY_GRAPH_ADAPTER=neo4j\n",
        )
        assert read_adapter_selections(tmp_path) == {"cache": "redis", "graph": "neo4j"}

    def test_ignores_comments_and_blanks(self, tmp_path):
        (tmp_path / ".env").write_text("# comment\n\nFACTORY_CACHE_ADAPTER=redis\n")
        assert read_adapter_selections(tmp_path) == {"cache": "redis"}

    def test_falls_back_to_env_example(self, tmp_path):
        (tmp_path / ".env.example").write_text("FACTORY_KB_ADAPTER=neo4j\n")
        assert read_adapter_selections(tmp_path) == {"kb": "neo4j"}

    def test_prefers_dotenv_over_example(self, tmp_path):
        (tmp_path / ".env").write_text("FACTORY_CACHE_ADAPTER=redis\n")
        (tmp_path / ".env.example").write_text("FACTORY_CACHE_ADAPTER=memory\n")
        assert read_adapter_selections(tmp_path) == {"cache": "redis"}

    def test_returns_empty_when_no_files(self, tmp_path):
        assert read_adapter_selections(tmp_path) == {}

    def test_handles_malformed_lines(self, tmp_path):
        (tmp_path / ".env").write_text("NOT_AN_ADAPTER=foo\n=broken\nFACTORY_CACHE_ADAPTER=redis\n")
        assert read_adapter_selections(tmp_path) == {"cache": "redis"}

    def test_case_insensitive_brick_name(self, tmp_path):
        (tmp_path / ".env").write_text("FACTORY_CACHE_ADAPTER=redis\n")
        assert "cache" in read_adapter_selections(tmp_path)

    def test_ignores_non_adapter_factory_vars(self, tmp_path):
        (tmp_path / ".env").write_text("FACTORY_API_HOST=0.0.0.0\nFACTORY_CACHE_ADAPTER=redis\n")
        assert read_adapter_selections(tmp_path) == {"cache": "redis"}


class TestResolveInfraFromBricks:
    def test_cache_redis_resolves(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"redis": {"services": ["redis"]}})
        assert resolve_infra_from_bricks(tmp_path, ["cache"], {"cache": "redis"}) == ["redis"]

    def test_networkx_no_infra(self, tmp_path):
        _write_brick_yaml(tmp_path, "graph", {"neo4j": {"services": ["neo4j"]}})
        assert resolve_infra_from_bricks(tmp_path, ["graph"], {"graph": "networkx"}) == []

    def test_neo4j_adapter_resolves(self, tmp_path):
        _write_brick_yaml(tmp_path, "graph", {"neo4j": {"services": ["neo4j"]}})
        assert resolve_infra_from_bricks(tmp_path, ["graph"], {"graph": "neo4j"}) == ["neo4j"]

    def test_deduplicates_overlapping_services(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"redis": {"services": ["redis"]}})
        _write_brick_yaml(tmp_path, "events", {"redis": {"services": ["redis"]}})
        result = resolve_infra_from_bricks(
            tmp_path, ["cache", "events"], {"cache": "redis", "events": "redis"},
        )
        assert result == ["redis"]

    def test_no_adapter_infra_entry(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"redis": {"services": ["redis"]}})
        assert resolve_infra_from_bricks(tmp_path, ["cache"], {"cache": "memory"}) == []

    def test_missing_brick_yaml_skipped(self, tmp_path):
        assert resolve_infra_from_bricks(tmp_path, ["nope"], {"nope": "redis"}) == []

    def test_empty_selections(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"redis": {"services": ["redis"]}})
        assert resolve_infra_from_bricks(tmp_path, ["cache"], {}) == []

    def test_output_is_sorted(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"redis": {"services": ["redis"]}})
        _write_brick_yaml(tmp_path, "graph", {"neo4j": {"services": ["neo4j"]}})
        result = resolve_infra_from_bricks(
            tmp_path, ["cache", "graph"], {"cache": "redis", "graph": "neo4j"},
        )
        assert result == sorted(result)

    def test_empty_services_list(self, tmp_path):
        _write_brick_yaml(tmp_path, "cache", {"aws": {"services": []}})
        assert resolve_infra_from_bricks(tmp_path, ["cache"], {"cache": "aws"}) == []


class TestAdapterAwareIntrospect:
    """Integration tests using real workspace companion_x project."""

    def test_reads_adapter_selections(self, workspace_root):
        info = introspect_project(workspace_root, "companion_x")
        assert isinstance(info.adapter_selections, dict)
        assert len(info.adapter_selections) > 0

    def test_infra_matches_selections(self, workspace_root):
        info = introspect_project(workspace_root, "companion_x")
        expected = resolve_infra_from_bricks(
            workspace_root, info.components, info.adapter_selections,
        )
        assert info.infra_services == expected

    def test_adapter_selections_populated(self, workspace_root):
        info = introspect_project(workspace_root, "companion_x")
        assert "cache" in info.adapter_selections


class TestAdapterAwareEnvExample:
    def test_includes_adapter_lines(self):
        info = ProjectInfo(
            name="test_proj", description="",
            components=["cache", "graph"],
            adapter_selections={"cache": "redis", "graph": "neo4j"},
            infra_services=["neo4j", "redis"],
        )
        content = render_env_example(info)
        assert "FACTORY_CACHE_ADAPTER=redis" in content
        assert "FACTORY_GRAPH_ADAPTER=neo4j" in content

    def test_only_selected_infra_env_vars(self):
        info = ProjectInfo(
            name="test_proj", description="",
            components=["cache"],
            adapter_selections={"cache": "redis"}, infra_services=["redis"],
        )
        content = render_env_example(info)
        assert "FACTORY_REDIS_URL" in content
        assert "FACTORY_NEO4J_URL" not in content

    def test_omits_adapter_section_when_empty(self):
        info = ProjectInfo(
            name="test_proj", description="",
            adapter_selections={}, infra_services=[],
        )
        assert "Adapter Selections" not in render_env_example(info)

    def test_filters_adapters_to_components_only(self):
        info = ProjectInfo(
            name="test_proj", description="",
            components=["cache"],
            adapter_selections={"cache": "redis", "unknown": "foo"},
            infra_services=["redis"],
        )
        content = render_env_example(info)
        assert "FACTORY_CACHE_ADAPTER=redis" in content
        assert "FACTORY_UNKNOWN_ADAPTER" not in content
