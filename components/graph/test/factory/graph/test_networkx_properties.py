"""Property-based tests for NetworkX graph adapter using Hypothesis."""

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

_settings = settings(max_examples=100, deadline=None)

from factory.graph.runtime.adapters.networkx_adapter import NetworkXGraph
from factory.graph.runtime.ports import Entity, Relationship

# --- Strategies ---
entity_ids = st.text(
    min_size=1, max_size=15, alphabet=st.characters(whitelist_categories=("L", "N")),
)
entity_types = st.sampled_from(["person", "document", "concept", "event"])
rel_types = st.sampled_from(["knows", "references", "contains", "triggers"])
props = st.fixed_dictionaries({})
entity_st = st.builds(
    Entity, id=entity_ids, type=entity_types, properties=props, labels=st.just([]),
)


def _ensure_distinct(src: Entity, tgt: Entity) -> Entity:
    """Return tgt with a distinct ID if it collides with src."""
    if src.id == tgt.id:
        return Entity(id=tgt.id + "_tgt", type=tgt.type, properties=tgt.properties)
    return tgt


# --- @given property tests ---

class TestNetworkXProperties:
    """Property-based tests for individual NetworkXGraph operations."""

    @given(entity=entity_st)
    @_settings
    def test_add_then_get_roundtrips(self, entity: Entity) -> None:
        """Adding an entity then getting it returns the same data."""
        graph = NetworkXGraph()
        graph.add_entity(entity)
        result = graph.get_entity(entity.id)
        assert result is not None
        assert result.id == entity.id
        assert result.type == entity.type
        assert result.properties == entity.properties

    @given(entity=entity_st)
    @_settings
    def test_delete_then_get_returns_none(self, entity: Entity) -> None:
        """Deleting an entity then getting it returns None."""
        graph = NetworkXGraph()
        graph.add_entity(entity)
        graph.delete_entity(entity.id)
        assert graph.get_entity(entity.id) is None

    @given(src=entity_st, tgt=entity_st, rel_id=entity_ids, rel_type=rel_types)
    @_settings
    def test_add_relationship_roundtrips(
        self, src: Entity, tgt: Entity, rel_id: str, rel_type: str,
    ) -> None:
        """Adding a relationship then getting it returns the same data."""
        tgt = _ensure_distinct(src, tgt)
        graph = NetworkXGraph()
        graph.add_entity(src)
        graph.add_entity(tgt)
        rel = Relationship(id=rel_id, type=rel_type, source_id=src.id, target_id=tgt.id)
        graph.add_relationship(rel)
        replacement = Entity(id=f"{tgt.id}_replacement", type=tgt.type)
        graph.add_entity(replacement)
        replacement_rel = Relationship(
            id=rel_id, type=rel_type, source_id=src.id, target_id=replacement.id,
        )
        graph.add_relationship(replacement_rel)
        result = graph.get_relationship(rel_id)
        assert result is not None
        assert result.id == rel_id and result.type == rel_type
        assert result.source_id == src.id and result.target_id == replacement.id
        assert graph.health_check().edge_count == 1

    @given(src=entity_st, tgt=entity_st, rel_id=entity_ids, rel_type=rel_types)
    @_settings
    def test_delete_relationship_then_get_returns_none(
        self, src: Entity, tgt: Entity, rel_id: str, rel_type: str,
    ) -> None:
        """Deleting a relationship then getting it returns None."""
        tgt = _ensure_distinct(src, tgt)
        graph = NetworkXGraph()
        graph.add_entity(src)
        graph.add_entity(tgt)
        rel = Relationship(id=rel_id, type=rel_type, source_id=src.id, target_id=tgt.id)
        graph.add_relationship(rel)
        graph.delete_relationship(rel_id)
        assert graph.get_relationship(rel_id) is None

    @given(entities=st.lists(entity_st, min_size=1, max_size=20), filter_type=entity_types)
    @_settings
    def test_find_entities_filters_by_type(
        self, entities: list[Entity], filter_type: str,
    ) -> None:
        """find_entities(entity_type=X) only returns entities of type X."""
        graph = NetworkXGraph()
        seen: set[str] = set()
        for e in entities:
            if e.id not in seen:
                graph.add_entity(e)
                seen.add(e.id)
        for r in graph.find_entities(entity_type=filter_type):
            assert r.type == filter_type

    @given(entity=entity_st, new_type=entity_types)
    @_settings
    def test_add_same_id_twice_updates(self, entity: Entity, new_type: str) -> None:
        """Adding an entity with the same ID twice overwrites (update semantics)."""
        graph = NetworkXGraph()
        graph.add_entity(entity)
        graph.add_entity(Entity(id=entity.id, type=new_type, properties={"updated": True}))
        result = graph.get_entity(entity.id)
        assert result is not None
        assert result.type == new_type
        assert result.properties.get("updated") is True


# --- RuleBasedStateMachine stateful test ---

class NetworkXGraphStateMachine(RuleBasedStateMachine):
    """Stateful test: arbitrary operation sequences on NetworkXGraph."""

    def __init__(self) -> None:
        super().__init__()
        self.graph: NetworkXGraph | None = None
        self.entities: dict[str, Entity] = {}
        # MultiDiGraph stores parallel edges independently by relationship ID.
        self.edges: dict[tuple[str, str, str], Relationship] = {}
        self.rel_id_to_edge: dict[str, tuple[str, str, str]] = {}

    @initialize()
    def init_graph(self) -> None:
        self.graph = NetworkXGraph()
        self.entities = {}
        self.edges = {}
        self.rel_id_to_edge = {}

    @rule(entity=entity_st)
    def add_entity(self, entity: Entity) -> None:
        self.graph.add_entity(entity)
        self.entities[entity.id] = entity

    @rule(data=st.data())
    def delete_entity(self, data: st.DataObject) -> None:
        if not self.entities:
            return
        eid = data.draw(st.sampled_from(sorted(self.entities.keys())))
        self.graph.delete_entity(eid)
        del self.entities[eid]
        for key in [k for k in self.edges if k[0] == eid or k[1] == eid]:
            self.rel_id_to_edge.pop(self.edges.pop(key).id, None)

    @rule(rel_id=entity_ids, rel_type=rel_types, data=st.data())
    def add_relationship(self, rel_id: str, rel_type: str, data: st.DataObject) -> None:
        if len(self.entities) < 2:
            return
        keys = sorted(self.entities.keys())
        src = data.draw(st.sampled_from(keys))
        tgt = data.draw(st.sampled_from([k for k in keys if k != src]))
        rel = Relationship(id=rel_id, type=rel_type, source_id=src, target_id=tgt)
        self.graph.add_relationship(rel)
        edge_key = (src, tgt, rel_id)
        prior_edge = self.rel_id_to_edge.pop(rel_id, None)
        if prior_edge is not None:
            self.edges.pop(prior_edge, None)
        self.edges[edge_key] = rel
        self.rel_id_to_edge[rel_id] = edge_key

    @rule(data=st.data())
    def delete_relationship(self, data: st.DataObject) -> None:
        if not self.rel_id_to_edge:
            return
        rid = data.draw(st.sampled_from(sorted(self.rel_id_to_edge.keys())))
        self.graph.delete_relationship(rid)
        self.edges.pop(self.rel_id_to_edge.pop(rid), None)

    @invariant()
    def node_count_matches(self) -> None:
        health = self.graph.health_check()
        assert health.node_count == len(self.entities)

    @invariant()
    def edge_count_matches(self) -> None:
        health = self.graph.health_check()
        assert health.edge_count == len(self.edges)

    @invariant()
    def all_model_entities_retrievable(self) -> None:
        for eid in self.entities:
            assert self.graph.get_entity(eid) is not None

    @invariant()
    def deleted_entities_return_none(self) -> None:
        assert self.graph.get_entity("__nonexistent_sentinel__") is None


TestNetworkXStateful = NetworkXGraphStateMachine.TestCase
TestNetworkXStateful.settings = settings(max_examples=100, stateful_step_count=30, deadline=None)
