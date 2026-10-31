"""
Property-based tests for YamlEvaluatorAdapter using Hypothesis.

Tests that the policy evaluation engine maintains key invariants
across arbitrary combinations of policies, actions, and resources:
  - Deny-dominance: any matching deny rule forces a deny decision
  - No-policy-default-deny: empty policies always deny
  - Wildcard-matches-all: "*" patterns match any input
  - Evaluate-explain-consistency: evaluate/explain agree on decision
  - Reload-replaces-policies: reload swaps the full policy set
  - Health-check-reflects-count: policy_count tracks loaded policies
  - Idempotent-evaluation: same inputs always produce same decision
"""

from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.permissions.runtime.evaluation.yaml_adapter import YamlEvaluatorAdapter
from factory.permissions.runtime.models import PolicyDefinition, Rule

# ---------------------------------------------------------------------------
# Strategies
# ---------------------------------------------------------------------------

_id = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
_action = _id
_rtype = _id
_SETTINGS = settings(max_examples=50)


@st.composite
def rule_st(draw: st.DrawFn, *, effect: str | None = None) -> Rule:
    eff = effect or draw(st.sampled_from(["allow", "deny"]))
    return Rule(
        id=draw(_id), effect=eff,
        actions=draw(st.lists(_action, min_size=1, max_size=3)),
        resource_types=draw(st.lists(_rtype, min_size=1, max_size=3)),
    )


@st.composite
def policy_st(draw: st.DrawFn) -> PolicyDefinition:
    return PolicyDefinition(
        id=draw(_id), name=draw(_id),
        rules=draw(st.lists(rule_st(), min_size=1, max_size=3)),
    )


def _ev(adapter, action, rtype):
    return adapter.evaluate(action=action, resource={"type": rtype, "id": "t"}, context={})


def _ex(adapter, action, rtype):
    return adapter.explain(action=action, resource={"type": rtype, "id": "t"}, context={})


# ---------------------------------------------------------------------------
# Properties
# ---------------------------------------------------------------------------


class TestNoPolicyDefaultDeny:
    """Empty policy list always returns deny."""

    @given(action=_action, rtype=_rtype)
    @_SETTINGS
    def test_empty_policies_deny(self, action: str, rtype: str) -> None:
        result = _ev(YamlEvaluatorAdapter([]), action, rtype)
        assert result["decision"] == "deny"
        assert result["reason"] == "no_matching_policy"


class TestDenyDominance:
    """If any deny rule matches, decision is always deny."""

    @given(action=_action, rtype=_rtype,
           extras=st.lists(rule_st(effect="allow"), max_size=3))
    @_SETTINGS
    def test_deny_overrides_allow(self, action, rtype, extras) -> None:
        rules = [
            Rule(id="a1", effect="allow", actions=[action], resource_types=[rtype]),
            Rule(id="d1", effect="deny", actions=[action], resource_types=[rtype]),
        ] + extras
        adapter = YamlEvaluatorAdapter([PolicyDefinition(id="p", name="p", rules=rules)])
        assert _ev(adapter, action, rtype)["decision"] == "deny"


class TestWildcardMatchesAll:
    """A rule with actions=["*"] and resource_types=["*"] matches anything."""

    @given(action=_action, rtype=_rtype,
           effect=st.sampled_from(["allow", "deny"]))
    @_SETTINGS
    def test_wildcard_matches(self, action, rtype, effect) -> None:
        rule = Rule(id="w", effect=effect, actions=["*"], resource_types=["*"])
        adapter = YamlEvaluatorAdapter([PolicyDefinition(id="p", name="p", rules=[rule])])
        assert _ev(adapter, action, rtype)["decision"] == effect


class TestEvaluateExplainConsistency:
    """evaluate() and explain() must agree on the decision."""

    @given(policies=st.lists(policy_st(), max_size=3),
           action=_action, rtype=_rtype)
    @_SETTINGS
    def test_decisions_match(self, policies, action, rtype) -> None:
        adapter = YamlEvaluatorAdapter(policies)
        assert _ev(adapter, action, rtype)["decision"] == _ex(adapter, action, rtype)["decision"]


class TestReloadReplacesPolicies:
    """After reload(), old policies no longer apply."""

    @given(action=_action, rtype=_rtype)
    @_SETTINGS
    def test_reload_clears_old(self, action, rtype) -> None:
        allow = Rule(id="a", effect="allow", actions=[action], resource_types=[rtype])
        adapter = YamlEvaluatorAdapter([PolicyDefinition(id="o", name="o", rules=[allow])])
        assert _ev(adapter, action, rtype)["decision"] == "allow"
        adapter.reload([])
        result = _ev(adapter, action, rtype)
        assert result["decision"] == "deny"
        assert result["reason"] == "no_matching_policy"


class TestHealthCheckReflectsCount:
    """health_check()["policy_count"] equals number of loaded policies."""

    @given(policies=st.lists(policy_st(), max_size=5))
    @_SETTINGS
    def test_count_matches(self, policies) -> None:
        adapter = YamlEvaluatorAdapter(policies)
        h = adapter.health_check()
        assert h["healthy"] is True and h["backend"] == "yaml"
        assert h["policy_count"] == len(policies)

    @given(initial=st.lists(policy_st(), max_size=3),
           reloaded=st.lists(policy_st(), max_size=3))
    @_SETTINGS
    def test_count_after_reload(self, initial, reloaded) -> None:
        adapter = YamlEvaluatorAdapter(initial)
        assert adapter.health_check()["policy_count"] == len(initial)
        adapter.reload(reloaded)
        assert adapter.health_check()["policy_count"] == len(reloaded)


class TestIdempotentEvaluation:
    """Same inputs always produce the same decision (no side effects)."""

    @given(policies=st.lists(policy_st(), max_size=3),
           action=_action, rtype=_rtype)
    @_SETTINGS
    def test_repeated_calls_same_result(self, policies, action, rtype) -> None:
        adapter = YamlEvaluatorAdapter(policies)
        first = _ev(adapter, action, rtype)
        second = _ev(adapter, action, rtype)
        assert first["decision"] == second["decision"]
        assert first["reason"] == second["reason"]
