"""
Property-based tests for CTFChallengeRules.

Verifies invariants via @given (stateless) and RuleBasedStateMachine (stateful):
- move_history length always matches number of apply_move calls
- Terminal state has no legal moves
- Correct flag → winner=1, reward=1.0, terminal=True
- Wrong flag → reward=-0.1 (not terminal unless max attempts)
- Max attempts exhaustion → terminal=True, winner=None, reward=-1.0
- Only valid actions accepted (execute, read_file, write_file, submit_flag)
- Game starts with status="active" and current_player=1
"""

import hashlib

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.games.runtime.adapters.ctf_challenge import CTFChallengeRules, CTF_ACTIONS
from factory.games.core import STATUS_ACTIVE, STATUS_FINISHED, CTF_PLAYER

rules = CTFChallengeRules()
game_ids = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
actions = st.sampled_from(list(CTF_ACTIONS))
commands = st.text(min_size=0, max_size=50)
flag_guesses = st.text(min_size=0, max_size=50)
max_attempts_st = st.integers(min_value=1, max_value=30)


def _flag_hash(flag: str) -> str:
    return hashlib.sha256(flag.encode()).hexdigest()


# ── Stateless properties ──────────────────────────────────────────────

@given(gid=game_ids)
@settings(max_examples=50)
def test_initial_state_is_active_player_one(gid: str):
    """Fresh game: status=active, current_player=1, empty history."""
    state = rules.create_initial_state(gid)
    assert state.game_type == "ctf_challenge"
    assert state.status == STATUS_ACTIVE
    assert state.current_player == CTF_PLAYER
    assert state.move_history == []


@given(gid=game_ids, action=actions, cmd=commands)
@settings(max_examples=50)
def test_valid_action_accepted(gid: str, action: str, cmd: str):
    """All four CTF actions are accepted on a fresh game."""
    state = rules.create_initial_state(gid)
    move = {"action": action, "command": cmd, "flag": cmd}
    result = rules.apply_move(state, CTF_PLAYER, move)
    assert result.valid


@given(gid=game_ids, bad=st.text(min_size=1, max_size=20).filter(lambda s: s not in CTF_ACTIONS))
@settings(max_examples=50)
def test_invalid_action_rejected(gid: str, bad: str):
    """Actions outside the valid set are rejected."""
    state = rules.create_initial_state(gid)
    result = rules.apply_move(state, CTF_PLAYER, {"action": bad})
    assert not result.valid
    assert result.error is not None


@given(gid=game_ids)
@settings(max_examples=50)
def test_wrong_player_rejected(gid: str):
    """Player != 1 is rejected (single-player game)."""
    state = rules.create_initial_state(gid)
    result = rules.apply_move(state, 2, {"action": "execute", "command": "ls"})
    assert not result.valid
    assert "single-player" in result.error.lower()


@given(gid=game_ids, flag=flag_guesses)
@settings(max_examples=50)
def test_correct_flag_wins(gid: str, flag: str):
    """Submitting the correct flag → terminal, winner=1, reward=1.0."""
    state = rules.create_initial_state(gid, config={"flag_hash": _flag_hash(flag)})
    result = rules.apply_move(state, CTF_PLAYER, {"action": "submit_flag", "flag": flag})
    assert result.valid and result.terminal
    assert result.state.winner == CTF_PLAYER
    assert result.reward[CTF_PLAYER] == 1.0
    assert result.state.status == STATUS_FINISHED


@given(gid=game_ids, flag=flag_guesses)
@settings(max_examples=50)
def test_wrong_flag_penalty_not_terminal(gid: str, flag: str):
    """Wrong flag on a fresh game → reward=-0.1, not terminal."""
    state = rules.create_initial_state(gid, config={"flag_hash": "impossible_hash", "max_attempts": 20})
    result = rules.apply_move(state, CTF_PLAYER, {"action": "submit_flag", "flag": flag})
    assert result.valid
    assert not result.terminal
    assert result.reward[CTF_PLAYER] == -0.1


@given(gid=game_ids, n=st.integers(min_value=1, max_value=10))
@settings(max_examples=50)
def test_max_attempts_exhaustion(gid: str, n: int):
    """Filling all attempts with non-flag actions → terminal, winner=None, reward=-1.0."""
    state = rules.create_initial_state(gid, config={"max_attempts": n, "flag_hash": "x"})
    for i in range(n):
        result = rules.apply_move(state, CTF_PLAYER, {"action": "execute", "command": f"cmd{i}"})
        state = result.state
    assert result.terminal
    assert result.state.winner is None
    assert result.reward[CTF_PLAYER] == -1.0
    assert rules.legal_moves(result.state) == []


@given(gid=game_ids)
@settings(max_examples=50)
def test_terminal_state_no_legal_moves(gid: str):
    """A finished game reports zero legal moves."""
    state = rules.create_initial_state(gid, config={"flag_hash": _flag_hash("f")})
    result = rules.apply_move(state, CTF_PLAYER, {"action": "submit_flag", "flag": "f"})
    assert result.terminal
    assert rules.legal_moves(result.state) == []


@given(gid=game_ids, n=max_attempts_st)
@settings(max_examples=50)
def test_evaluate_tracks_attempts(gid: str, n: int):
    """evaluate() reflects attempts used and remaining."""
    state = rules.create_initial_state(gid, config={"max_attempts": n})
    ev = rules.evaluate(state)
    assert ev["attempts_used"] == 0
    assert ev["attempts_remaining"] == n
    assert ev["solved"] is False


# ── Stateful machine ─────────────────────────────────────────────────

class CTFChallengeMachine(RuleBasedStateMachine):
    """Fuzz random CTF action sequences and verify invariants."""

    def __init__(self):
        super().__init__()
        self.rules = CTFChallengeRules()
        self.state = None
        self.move_count = 0
        self.max_attempts = 0

    @initialize(n=st.integers(min_value=3, max_value=15))
    def start_game(self, n):
        self.max_attempts = n
        self.state = self.rules.create_initial_state(
            "prop-ctf", config={"max_attempts": n, "flag_hash": "no_match"},
        )
        self.move_count = 0

    @rule(action=actions, cmd=commands, flag=flag_guesses)
    def play_action(self, action, cmd, flag):
        if self.state.status != STATUS_ACTIVE:
            return
        move = {"action": action, "command": cmd, "path": cmd, "content": cmd, "flag": flag}
        result = self.rules.apply_move(self.state, CTF_PLAYER, move)
        if result.valid:
            self.state = result.state
            self.move_count += 1

    @invariant()
    def history_length_matches(self):
        if self.state is not None:
            assert len(self.state.move_history) == self.move_count

    @invariant()
    def terminal_means_no_moves(self):
        if self.state is not None and self.state.status != STATUS_ACTIVE:
            assert self.rules.legal_moves(self.state) == []

    @invariant()
    def active_means_under_max(self):
        if self.state is not None and self.state.status == STATUS_ACTIVE:
            assert len(self.state.move_history) < self.max_attempts


TestCTFChallengeStateful = CTFChallengeMachine.TestCase
TestCTFChallengeStateful.settings = settings(max_examples=50, stateful_step_count=15)
