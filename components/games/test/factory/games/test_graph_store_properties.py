"""
Property tests for GraphGameStore adapter.

Properties: save/load roundtrip, save idempotency, delete semantics,
list_games status filtering, JSON serialization losslessness.
"""

from __future__ import annotations

from unittest.mock import patch

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, invariant

from factory.games.runtime.adapters.graph_store import (
    GraphGameStore, _serialize_props, _deserialize_state,
)
from factory.games.runtime.ports import GameState
from factory.graph.mcp.core_models import DeleteOutcomeData, EntityData, EntityLookupData, EntitySearchData
from factory.mcp_utils.runtime.tool_result import ToolResult

# ── Strategies ──────────────────────────────────────────────────────

_ids = st.text(min_size=1, max_size=20,
               alphabet=st.characters(whitelist_categories=("L", "N")))
_types = st.sampled_from(["connect_four", "ctf_challenge"])
_statuses = st.sampled_from(["active", "finished", "draw"])
_boards = st.lists(st.lists(st.integers(0, 2), min_size=1, max_size=7),
                   min_size=1, max_size=6)
_players = st.dictionaries(st.integers(1, 4),
                           st.text(min_size=1, max_size=10), max_size=4)
_moves = st.lists(st.fixed_dictionaries({"column": st.integers(0, 6)}),
                  max_size=5)
_configs = st.fixed_dictionaries({}, optional={"difficulty": st.integers(1, 5)})


@st.composite
def game_states(draw, status=None):
    return GameState(
        game_id=draw(_ids), game_type=draw(_types), board=draw(_boards),
        current_player=draw(st.integers(1, 2)),
        status=status or draw(_statuses),
        winner=draw(st.one_of(st.none(), st.integers(1, 2))),
        move_history=draw(_moves), players=draw(_players),
        config=draw(_configs),
        created_at="2025-01-01T00:00:00", updated_at="2025-01-01T00:00:00",
    )


# ── Mock invoker ────────────────────────────────────────────────────

class _FakeGraph:
    """In-memory mock of graph brick MCP tool responses."""
    def __init__(self):
        self.entities: dict[str, dict] = {}

    def __call__(self, tool_name: str, **kw):
        if tool_name == "graph_graph_add_entity":
            eid = kw["entity_id"]
            self.entities[eid] = {"properties": kw["properties"]}
            return {"created": True}
        if tool_name == "graph_graph_get_entity":
            ent = self.entities.get(kw["entity_id"])
            if ent is None:
                return ToolResult(data=EntityLookupData(
                    found=False, entity_id=kw["entity_id"],
                ))
            return ToolResult(data=EntityLookupData(
                found=True,
                entity_id=kw["entity_id"],
                entity=EntityData(
                    id=kw["entity_id"], type="GameSession", properties=ent["properties"],
                ),
            ))
        if tool_name == "graph_graph_find_entities":
            entities = [
                EntityData(id=entity_id, type="GameSession", properties=entity["properties"])
                for entity_id, entity in self.entities.items()
            ]
            return ToolResult(data=EntitySearchData(entities=entities, count=len(entities)))
        if tool_name == "graph_graph_delete_entity":
            deleted = kw["entity_id"] in self.entities
            if deleted:
                del self.entities[kw["entity_id"]]
            return ToolResult(data=DeleteOutcomeData(
                success=deleted, identifier=kw["entity_id"],
            ))
        if tool_name == "graph_graph_health_check":
            return {"healthy": True, "node_count": len(self.entities)}
        return {}


_PATCH_TARGET = "factory.games.runtime.adapters.graph_store._get_invoker"


def _make():
    """Return (store, context-manager patcher)."""
    fake = _FakeGraph()
    return GraphGameStore(), patch(_PATCH_TARGET, return_value=fake)


# ── Stateless properties ───────────────────────────────────────────

@given(state=game_states())
@settings(max_examples=50)
def test_save_load_roundtrip(state: GameState):
    """save then load preserves all fields."""
    store, p = _make()
    with p:
        store.save(state)
        loaded = store.load(state.game_id)
    assert loaded is not None
    for attr in ("game_id", "game_type", "board", "status", "winner",
                 "move_history", "players", "config"):
        assert getattr(loaded, attr) == getattr(state, attr), attr


@given(state=game_states())
@settings(max_examples=50)
def test_save_idempotent(state: GameState):
    """Saving twice doesn't create duplicates."""
    store, p = _make()
    with p:
        store.save(state)
        store.save(state)
        assert [g.game_id for g in store.list_games()].count(state.game_id) == 1


@given(state=game_states())
@settings(max_examples=50)
def test_delete_then_load_returns_none(state: GameState):
    """After delete, load returns None; second delete returns False."""
    store, p = _make()
    with p:
        store.save(state)
        assert store.delete(state.game_id) is True
        assert store.load(state.game_id) is None
        assert store.delete(state.game_id) is False


@given(active=st.lists(game_states(status="active"), max_size=3),
       finished=st.lists(game_states(status="finished"), max_size=3))
@settings(max_examples=30)
def test_list_games_status_filter(active, finished):
    """list_games(status=X) returns only matching games."""
    store, p = _make()
    with p:
        seen: set[str] = set()
        for s in active + finished:
            if s.game_id not in seen:
                store.save(s)
                seen.add(s.game_id)
        assert all(g.status == "active" for g in store.list_games(status="active"))


@given(state=game_states())
@settings(max_examples=50)
def test_json_serialization_lossless(state: GameState):
    """Serialize then deserialize complex fields without loss."""
    props = _serialize_props(state)
    for f in ("board", "move_history", "players", "config"):
        assert isinstance(props[f], str)
    restored = _deserialize_state({"properties": props})
    assert restored.board == state.board
    assert restored.move_history == state.move_history
    assert restored.players == state.players
    assert restored.config == state.config


# ── Stateful machine ───────────────────────────────────────────────

class GraphStoreMachine(RuleBasedStateMachine):
    """Random save/load/list/delete sequences with model checking."""

    def __init__(self):
        super().__init__()
        self.fake = _FakeGraph()
        self.store = GraphGameStore()
        self.model: dict[str, GameState] = {}
        self._p = patch(_PATCH_TARGET, return_value=self.fake)
        self._p.start()

    def teardown(self):
        self._p.stop()

    @rule(state=game_states())
    def save_game(self, state):
        self.store.save(state)
        self.model[state.game_id] = state

    @rule(gid=_ids)
    def delete_game(self, gid):
        assert self.store.delete(gid) == (gid in self.model)
        self.model.pop(gid, None)

    @rule(gid=_ids)
    def load_game(self, gid):
        loaded = self.store.load(gid)
        if gid in self.model:
            assert loaded is not None and loaded.game_id == gid
        else:
            assert loaded is None

    @invariant()
    def entity_count_matches(self):
        assert len(self.store.list_games()) == len(self.model)


TestGraphStoreStateful = GraphStoreMachine.TestCase
TestGraphStoreStateful.settings = settings(max_examples=50, stateful_step_count=20)
