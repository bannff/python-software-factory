"""
Property-based tests for ConnectFourRules and MemoryGameStore.

Uses Hypothesis to fuzz inputs and verify invariants that must hold
across all valid (and invalid) operation sequences.
"""

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.games.runtime.adapters.connect_four import ConnectFourRules
from factory.games.runtime.adapters.memory_store import MemoryGameStore
from factory.games.runtime.ports import GameState
from factory.games.core import (
    DEFAULT_COLS, DEFAULT_ROWS, EMPTY, PLAYER_1, PLAYER_2,
    STATUS_ACTIVE, STATUS_DRAW, STATUS_FINISHED,
)

rules = ConnectFourRules()
game_ids = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
columns = st.integers(min_value=0, max_value=DEFAULT_COLS - 1)

# \u2500\u2500 ConnectFourRules: stateless properties \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

@given(gid=game_ids)
@settings(max_examples=50)
def test_initial_board_all_empty(gid: str):
    """Every cell on a fresh board must be EMPTY."""
    state = rules.create_initial_state(gid)
    assert state.game_type == "connect_four"
    assert state.status == STATUS_ACTIVE
    assert state.current_player == PLAYER_1
    for row in state.board:
        assert all(cell == EMPTY for cell in row)


@given(gid=game_ids)
@settings(max_examples=50)
def test_legal_moves_match_open_columns(gid: str):
    """Legal move count equals number of non-full top-row columns."""
    state = rules.create_initial_state(gid)
    moves = rules.legal_moves(state)
    open_cols = sum(1 for c in range(DEFAULT_COLS) if state.board[0][c] == EMPTY)
    assert len(moves) == open_cols


@given(gid=game_ids, col=columns)
@settings(max_examples=50)
def test_valid_move_toggles_player(gid: str, col: int):
    """After a valid move the current player switches."""
    state = rules.create_initial_state(gid)
    result = rules.apply_move(state, PLAYER_1, {"column": col})
    assert result.valid
    if not result.terminal:
        assert result.state.current_player == PLAYER_2


@given(gid=game_ids, col=st.integers().filter(lambda c: c < 0 or c >= DEFAULT_COLS))
@settings(max_examples=50)
def test_invalid_column_rejected(gid: str, col: int):
    """Out-of-range columns must be rejected."""
    state = rules.create_initial_state(gid)
    result = rules.apply_move(state, PLAYER_1, {"column": col})
    assert not result.valid
    assert result.error is not None


@given(gid=game_ids, col=columns)
@settings(max_examples=50)
def test_full_column_rejected(gid: str, col: int):
    """Dropping into a full column must fail."""
    state = rules.create_initial_state(gid)
    # Fill the column by alternating players
    player = PLAYER_1
    for _ in range(DEFAULT_ROWS):
        r = rules.apply_move(state, player, {"column": col})
        assert r.valid
        state = r.state
        if r.terminal:
            return  # game ended before column filled; property vacuously holds
        player = state.current_player
    result = rules.apply_move(state, player, {"column": col})
    assert not result.valid
    assert "full" in result.error.lower()


@given(gid=game_ids)
@settings(max_examples=50)
def test_terminated_game_has_no_legal_moves(gid: str):
    """A finished or drawn game must report zero legal moves."""
    state = rules.create_initial_state(gid)
    # Force a vertical win for PLAYER_1 in col 0, PLAYER_2 in col 1
    for _ in range(3):
        state = rules.apply_move(state, state.current_player, {"column": 0}).state
        state = rules.apply_move(state, state.current_player, {"column": 1}).state
    result = rules.apply_move(state, state.current_player, {"column": 0})
    assert result.terminal
    assert result.state.status in (STATUS_FINISHED, STATUS_DRAW)
    assert rules.legal_moves(result.state) == []


# \u2500\u2500 MemoryGameStore: CRUD properties \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

def _make_state(gid: str, status: str = STATUS_ACTIVE) -> GameState:
    """Helper to build a minimal GameState for store tests."""
    state = rules.create_initial_state(gid)
    state.status = status
    return state


@given(gid=game_ids)
@settings(max_examples=50)
def test_save_load_roundtrip(gid: str):
    """save then load returns the same state."""
    store = MemoryGameStore()
    state = _make_state(gid)
    store.save(state)
    loaded = store.load(gid)
    assert loaded is not None
    assert loaded.game_id == state.game_id
    assert loaded.board == state.board
    assert loaded.status == state.status


@given(gid=game_ids)
@settings(max_examples=50)
def test_delete_removes(gid: str):
    """After delete, load returns None."""
    store = MemoryGameStore()
    state = _make_state(gid)
    store.save(state)
    assert store.delete(gid) is True
    assert store.load(gid) is None
    assert store.delete(gid) is False  # second delete returns False


@given(
    active=st.integers(min_value=0, max_value=5),
    finished=st.integers(min_value=0, max_value=5),
)
@settings(max_examples=50)
def test_health_check_counts_active(active: int, finished: int):
    """health_check().active_games matches the number of active games."""
    store = MemoryGameStore()
    for i in range(active):
        store.save(_make_state(f"a{i}", STATUS_ACTIVE))
    for i in range(finished):
        store.save(_make_state(f"f{i}", STATUS_FINISHED))
    health = store.health_check()
    assert health.healthy is True
    assert health.active_games == active


# \u2500\u2500 ConnectFourRules: stateful machine \u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500\u2500

class ConnectFourMachine(RuleBasedStateMachine):
    """Play random legal moves and verify invariants after each step."""

    def __init__(self):
        super().__init__()
        self.rules = ConnectFourRules()
        self.state: GameState | None = None
        self.move_count = 0

    @initialize()
    def start_game(self):
        self.state = self.rules.create_initial_state("prop-game")
        self.move_count = 0

    @rule(col=columns)
    def play_move(self, col: int):
        if self.state.status != STATUS_ACTIVE:
            return
        result = self.rules.apply_move(self.state, self.state.current_player, {"column": col})
        if result.valid:
            self.state = result.state
            self.move_count += 1

    @invariant()
    def move_history_length_matches(self):
        if self.state is not None:
            assert len(self.state.move_history) == self.move_count

    @invariant()
    def board_token_count_matches_moves(self):
        if self.state is None:
            return
        tokens = sum(1 for row in self.state.board for c in row if c != EMPTY)
        assert tokens == self.move_count

    @invariant()
    def active_game_has_legal_moves(self):
        if self.state is not None and self.state.status == STATUS_ACTIVE:
            assert len(self.rules.legal_moves(self.state)) > 0


TestConnectFourStateful = ConnectFourMachine.TestCase
TestConnectFourStateful.settings = settings(max_examples=50, stateful_step_count=30)
