"""Tests for the portable Graph MCP server."""

import asyncio

import pytest

from factory.mcp_utils.runtime.schema_migration import SchemaMigrationError
from factory.graph.server import create_mcp_server
from factory.graph.runtime.runtime import GraphRuntime, reset_runtime


_RETIRED_TOOLS = {
    "graph_query", "graph_record_run_findings",
    "graph_list_vector_indexes", "graph_vector_search", "graph_get_node_embedding",
    "graph_create_vector_index", "graph_drop_vector_index", "graph_set_embedding",
    "graph_list_gds_algorithms", "graph_run_fastrp", "graph_run_graphsage",
    "graph_run_node2vec", "graph_hybrid_search",
}


def _call_tool(server, tool_name: str, **kwargs):
    tool = asyncio.run(server.get_tool(tool_name))
    if tool is None:
        raise ValueError(f"Tool '{tool_name}' not found.")
    return tool.fn(**kwargs)


class TestMCPContract:
    def setup_method(self) -> None:
        reset_runtime()
        self.server = create_mcp_server()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_get_capabilities(self) -> None:
        result = _call_tool(self.server, "graph_get_capabilities")
        assert result.ok and result.data is not None
        assert result.data.name == "graph"
        assert result.data.version
        assert result.data.backends
        assert result.data.features

    def test_health_check_no_graphs(self) -> None:
        result = _call_tool(self.server, "graph_health_check")
        assert result.ok and result.data is not None
        assert result.data.healthy is True
        assert result.data.graphs == {}

    def test_describe_config_schema(self) -> None:
        result = _call_tool(self.server, "graph_describe_config_schema")
        assert result.ok and result.data is not None
        assert result.data.type == "object"
        assert "backend" in result.data.properties


class TestGraphTools:
    def setup_method(self) -> None:
        reset_runtime()
        self.server = create_mcp_server()

    def teardown_method(self) -> None:
        reset_runtime()

    def test_add_and_get_entity(self) -> None:
        result = _call_tool(self.server, "graph_add_entity", entity_id="e1",
                            entity_type="Person", properties={"name": "Alice"})
        assert result.ok and result.data is not None
        assert result.data.id == "e1"

        lookup = _call_tool(self.server, "graph_get_entity", entity_id="e1")
        assert lookup.ok and lookup.data is not None
        assert lookup.data.found is True
        assert lookup.data.entity is not None
        assert lookup.data.entity.id == "e1"

    def test_get_nonexistent_entity(self) -> None:
        result = _call_tool(self.server, "graph_get_entity", entity_id="nonexistent")
        assert result.ok and result.data is not None
        assert result.data.found is False

    def test_add_relationship_and_get_neighbors(self) -> None:
        for entity_id in ("e1", "e2"):
            _call_tool(self.server, "graph_add_entity", entity_id=entity_id,
                       entity_type="Person")
        result = _call_tool(self.server, "graph_add_relationship", relationship_id="r1",
                            relationship_type="KNOWS", source_id="e1", target_id="e2")
        assert result.ok and result.data is not None
        assert result.data.id == "r1"

        neighbors = _call_tool(self.server, "graph_get_neighbors", entity_id="e1",
                               direction="out", limit=1)
        assert neighbors.ok and neighbors.data is not None
        assert [entity.id for entity in neighbors.data.neighbors] == ["e2"]
        with pytest.raises(SchemaMigrationError, match="less than or equal to 200"):
            _call_tool(self.server, "graph_get_neighbors", entity_id="e1", limit=201)

    def test_find_path(self) -> None:
        for entity_id in ("e1", "e2", "e3"):
            _call_tool(self.server, "graph_add_entity", entity_id=entity_id,
                       entity_type="Person")
        _call_tool(self.server, "graph_add_relationship", relationship_id="r1",
                   relationship_type="KNOWS", source_id="e1", target_id="e2")
        _call_tool(self.server, "graph_add_relationship", relationship_id="r2",
                   relationship_type="KNOWS", source_id="e2", target_id="e3")
        result = _call_tool(self.server, "graph_find_path", source_id="e1", target_id="e3")
        assert result.ok and result.data is not None
        assert result.data.found is True
        assert result.data.length == 2


@pytest.mark.parametrize("backend", ["networkx", "persistent_networkx", "neo4j"])
def test_retired_tools_are_absent_for_every_backend(backend: str) -> None:
    runtime = GraphRuntime({"default_backend": backend})
    names = {tool.name for tool in asyncio.run(create_mcp_server(runtime).list_tools())}
    assert not _RETIRED_TOOLS & names
