"""Canary: generic fallback for unknown domains (bd python-factory-216ti).

When no verifier is registered for a finding's domain, the oracle returns
the finding's state UNCHANGED with a "no verifier registered" note and
NEVER raises — no hardcoded domain branch anywhere in the path.
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st

from factory.oracle.core import FINDING_STATES
from factory.oracle.runtime.registry import VerifierRegistry
from factory.oracle.runtime.runtime import OracleRuntime

_settings = settings(max_examples=80, deadline=None)
_states = st.sampled_from(sorted(FINDING_STATES))
_domains = st.text(min_size=0, max_size=12)


def _runtime() -> OracleRuntime:
    # Fresh empty registry → every domain is a miss → generic fallback.
    return OracleRuntime(registry=VerifierRegistry())


class TestGenericFallback:
    """Unknown domain → state unchanged, no raise."""

    @given(state=_states, domain=_domains)
    @_settings
    def test_unknown_domain_leaves_state_unchanged(
        self, state: str, domain: str,
    ) -> None:
        finding = {"id": "f-1", "state": state, "domain": domain}
        outcome = _runtime().verify(finding, domain=domain)
        assert outcome["state"] == state  # unchanged
        assert outcome["verifier"] == "generic-fallback"
        assert "no verifier registered" in outcome["evidence"]

    @given(finding=st.dictionaries(st.text(max_size=8), st.text(max_size=8)))
    @_settings
    def test_never_raises_on_arbitrary_finding(self, finding: dict) -> None:
        """Arbitrary finding shapes never raise; always a neutral outcome."""
        outcome = _runtime().verify(finding, domain="totally-unknown")
        assert "state" in outcome and "verifier" in outcome

    def test_missing_state_defaults_to_candidate(self) -> None:
        """A finding with no state degrades to the initial neutral state."""
        outcome = _runtime().verify({"id": "f-2"}, domain="unknown")
        assert outcome["state"] == "candidate"

    def test_raising_verifier_is_contained(self) -> None:
        """A verifier that raises is downgraded, not propagated."""
        class Boom:
            name = "boom"

            def verify(self, finding, context):
                raise RuntimeError("kaboom")

        reg = VerifierRegistry()
        reg.register("x", Boom())
        outcome = OracleRuntime(registry=reg).verify(
            {"id": "f", "state": "verifying"}, domain="x",
        )
        assert outcome["state"] == "verifying"
        assert "kaboom" in outcome["evidence"]
