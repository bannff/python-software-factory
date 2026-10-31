"""Property-based tests for security game adapters.

Invariants: initial state valid, correct finding → positive reward,
false positive → negative reward, all vulns found → terminal,
evaluate() 4 axes in [0,1], max actions → terminal, wrong player rejected.
"""

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.games.runtime.adapters.security_base import (
    SecurityGameRules, SECURITY_PLAYER, VALID_ACTIONS,
)
from factory.games.runtime.adapters.sql_injection import SQLInjectionRules
from factory.games.runtime.adapters.xss_hunter import XSSHunterRules
from factory.games.runtime.adapters.command_injection import CommandInjectionRules
from factory.games.runtime.adapters.ssti import SSTIRules
from factory.games.runtime.adapters.idor_detective import IDORDetectiveRules
from factory.games.runtime.adapters.path_traversal import PathTraversalRules
from factory.games.runtime.adapters.finding_triage import FindingTriageRules
from factory.games.core import STATUS_ACTIVE, STATUS_FINISHED

game_ids = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
actions = st.sampled_from(list(VALID_ACTIONS))
ALL_ADAPTERS = [SQLInjectionRules, XSSHunterRules, CommandInjectionRules,
                SSTIRules, IDORDetectiveRules, PathTraversalRules]
adapter_st = st.sampled_from(ALL_ADAPTERS)
vuln_types = st.sampled_from(["sqli", "xss", "cmdi", "ssti", "idor", "traversal"])
files = st.sampled_from(["app.py", "views.py", "api.py", "handler.py"])
lines = st.integers(min_value=1, max_value=200)

_SINGLE_GT = {"vulnerabilities": [{"id": "V1", "type": "sqli", "location": "a.py:1",
              "severity": "high"}], "false_positives": ["FP-001"]}


@st.composite
def ground_truth(draw):
    n = draw(st.integers(min_value=1, max_value=4))
    vulns = [{"id": f"V{i+1}", "type": draw(vuln_types),
              "location": f"{draw(files)}:{draw(lines)}", "severity": "high"} for i in range(n)]
    fps = [f"FP-{i+1:03d}" for i in range(draw(st.integers(min_value=0, max_value=2)))]
    return {"vulnerabilities": vulns, "false_positives": fps}


@given(cls=adapter_st, gid=game_ids)
@settings(max_examples=50)
def test_initial_state_valid(cls, gid):
    a = cls()
    s = a.create_initial_state(gid)
    assert s.status == STATUS_ACTIVE
    assert s.current_player == SECURITY_PLAYER
    assert s.move_history == []
    assert s.game_type == a.game_type


@given(cls=adapter_st, gid=game_ids, gt=ground_truth())
@settings(max_examples=50)
def test_correct_finding_positive_reward(cls, gid, gt):
    a, v = cls(), gt["vulnerabilities"][0]
    s = a.create_initial_state(gid, config={"ground_truth": gt})
    r = a.apply_move(s, SECURITY_PLAYER,
                     {"action": "submit_finding", "type": v["type"], "location": v["location"]})
    assert r.valid and r.reward[SECURITY_PLAYER] > 0


@given(cls=adapter_st, gid=game_ids)
@settings(max_examples=50)
def test_false_positive_negative_reward(cls, gid):
    a = cls()
    s = a.create_initial_state(gid, config={"ground_truth": _SINGLE_GT})
    r = a.apply_move(s, SECURITY_PLAYER,
                     {"action": "submit_finding", "finding_id": "FP-001", "type": "x", "location": "z:1"})
    assert r.valid and r.reward[SECURITY_PLAYER] == -0.5


@given(cls=adapter_st, gid=game_ids)
@settings(max_examples=50)
def test_no_match_small_penalty(cls, gid):
    a = cls()
    gt = {"vulnerabilities": [{"id": "V1", "type": "sqli", "location": "a.py:1",
          "severity": "high"}], "false_positives": []}
    s = a.create_initial_state(gid, config={"ground_truth": gt})
    r = a.apply_move(s, SECURITY_PLAYER,
                     {"action": "submit_finding", "type": "nonexistent", "location": "z.py:999"})
    assert r.valid and r.reward[SECURITY_PLAYER] == -0.1


@given(cls=adapter_st, gid=game_ids, gt=ground_truth())
@settings(max_examples=50)
def test_find_all_vulns_terminates(cls, gid, gt):
    a = cls()
    s = a.create_initial_state(gid, config={"ground_truth": gt, "max_actions": 50})
    for v in gt["vulnerabilities"]:
        r = a.apply_move(s, SECURITY_PLAYER,
                         {"action": "submit_finding", "type": v["type"], "location": v["location"]})
        s = r.state
    assert r.terminal and s.status == STATUS_FINISHED


@given(cls=adapter_st, gid=game_ids, gt=ground_truth())
@settings(max_examples=50)
def test_evaluate_axes_bounded(cls, gid, gt):
    a = cls()
    s = a.create_initial_state(gid, config={"ground_truth": gt})
    ev = a.evaluate(s)
    for axis in ("correctness", "evidence", "completeness", "efficiency"):
        assert 0.0 <= ev[axis] <= 1.0, f"{axis}={ev[axis]}"


@given(gid=game_ids, n=st.integers(min_value=1, max_value=8))
@settings(max_examples=50)
def test_max_actions_exhaustion(gid, n):
    a = SQLInjectionRules()
    s = a.create_initial_state(gid, config={"max_actions": n})
    for _ in range(n):
        r = a.apply_move(s, SECURITY_PLAYER, {"action": "analyze_code"})
        s = r.state
    assert r.terminal and s.status == STATUS_FINISHED


@given(gid=game_ids)
@settings(max_examples=50)
def test_wrong_player_rejected(gid):
    a = SQLInjectionRules()
    s = a.create_initial_state(gid)
    r = a.apply_move(s, 2, {"action": "analyze_code"})
    assert not r.valid and "single-player" in r.error.lower()


@given(gid=game_ids, bad=st.text(min_size=1, max_size=20).filter(lambda s: s not in VALID_ACTIONS))
@settings(max_examples=50)
def test_invalid_action_rejected(gid, bad):
    r = SQLInjectionRules().create_initial_state(gid)
    res = SQLInjectionRules().apply_move(r, SECURITY_PLAYER, {"action": bad})
    assert not res.valid


@given(gid=game_ids)
@settings(max_examples=50)
def test_triage_correct_classification(gid):
    a = FindingTriageRules()
    gt = {"vulnerabilities": [], "false_positives": [],
          "findings_to_triage": [{"id": "F1", "label": "tp"}, {"id": "F2", "label": "fp"}]}
    s = a.create_initial_state(gid, config={"ground_truth": gt, "max_actions": 20})
    r = a.apply_move(s, SECURITY_PLAYER,
                     {"action": "submit_finding", "finding_id": "F1", "classification": "tp"})
    assert r.valid and r.reward[SECURITY_PLAYER] == 1.0


@given(gid=game_ids)
@settings(max_examples=50)
def test_triage_wrong_classification(gid):
    a = FindingTriageRules()
    gt = {"vulnerabilities": [], "false_positives": [],
          "findings_to_triage": [{"id": "F1", "label": "tp"}]}
    s = a.create_initial_state(gid, config={"ground_truth": gt, "max_actions": 20})
    r = a.apply_move(s, SECURITY_PLAYER,
                     {"action": "submit_finding", "finding_id": "F1", "classification": "fp"})
    assert r.valid and r.reward[SECURITY_PLAYER] == -0.3


class SecurityGameMachine(RuleBasedStateMachine):
    def __init__(self):
        super().__init__()
        self.adapter = self.state = None
        self.move_count = self.max_actions = 0

    @initialize(n=st.integers(min_value=3, max_value=12))
    def start_game(self, n):
        self.adapter, self.max_actions, self.move_count = SQLInjectionRules(), n, 0
        self.state = self.adapter.create_initial_state(
            "prop-sec", config={"ground_truth": _SINGLE_GT, "max_actions": n})

    @rule(action=actions)
    def play_action(self, action):
        if self.state.status != STATUS_ACTIVE:
            return
        r = self.adapter.apply_move(self.state, SECURITY_PLAYER,
                                    {"action": action, "type": "sqli", "location": "a.py:1"})
        if r.valid:
            self.state, self.move_count = r.state, self.move_count + 1

    @invariant()
    def history_matches(self):
        if self.state:
            assert len(self.state.move_history) == self.move_count

    @invariant()
    def terminal_means_no_moves(self):
        if self.state and self.state.status != STATUS_ACTIVE:
            assert self.adapter.legal_moves(self.state) == []


TestSecurityGameStateful = SecurityGameMachine.TestCase
TestSecurityGameStateful.settings = settings(max_examples=50, stateful_step_count=15)
