"""Hypothesis property-based tests for MemoryFindingPersistence.

Properties verified:
- Store-then-retrieve roundtrip (persist → get returns same data)
- Persist idempotency (same ID twice → last write wins)
- Severity filtering (get_findings(severity=X) returns only matching)
- Limit enforcement (list_analyses(limit=N) returns at most N)
- Health check count tracks persisted analyses
- Stateful: model dict stays in sync with adapter across arbitrary op sequences
"""

from __future__ import annotations

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, rule, initialize, invariant

from factory.security.runtime.adapters.memory_persistence import MemoryFindingPersistence

# -- Strategies --

SEVERITIES = ["critical", "high", "medium", "low", "info"]
ANALYSIS_TYPES = ["code_analysis", "threat_model", "pen_test", "recon"]

id_st = st.text(min_size=1, max_size=20, alphabet=st.characters(whitelist_categories=("L", "N")))
type_st = st.sampled_from(ANALYSIS_TYPES)
target_st = st.text(min_size=1, max_size=50)
severity_st = st.sampled_from(SEVERITIES)
summary_st = st.one_of(st.none(), st.text(max_size=100))

finding_st = st.fixed_dictionaries({
    "id": id_st,
    "severity": severity_st,
    "title": st.text(min_size=1, max_size=40),
    "description": st.text(max_size=80),
})
findings_st = st.lists(finding_st, min_size=0, max_size=8)


# -- @given property tests --


@given(aid=id_st, atype=type_st, tgt=target_st, findings=findings_st, summary=summary_st)
@settings(max_examples=50)
def test_roundtrip_persist_then_get(aid, atype, tgt, findings, summary):
    """persist_analysis then get_analysis returns the same record."""
    store = MemoryFindingPersistence()
    store.persist_analysis(aid, atype, tgt, findings, summary)
    got = store.get_analysis(aid)
    assert got is not None
    assert got["analysis_id"] == aid
    assert got["analysis_type"] == atype
    assert got["target"] == tgt
    assert got["findings"] == findings
    assert got["summary"] == summary
    assert got["finding_count"] == len(findings)


@given(
    aid=id_st, tgt=target_st,
    f1=findings_st, f2=findings_st,
    s1=summary_st, s2=summary_st,
)
@settings(max_examples=50)
def test_persist_idempotency_last_write_wins(aid, tgt, f1, f2, s1, s2):
    """Persisting the same analysis_id twice overwrites with the latest data."""
    store = MemoryFindingPersistence()
    store.persist_analysis(aid, "code_analysis", tgt, f1, s1)
    store.persist_analysis(aid, "threat_model", tgt, f2, s2)
    got = store.get_analysis(aid)
    assert got["analysis_type"] == "threat_model"
    assert got["findings"] == f2
    assert got["summary"] == s2


@given(
    aid=id_st, atype=type_st, tgt=target_st,
    findings=st.lists(finding_st, min_size=1, max_size=8),
    sev=severity_st,
)
@settings(max_examples=50)
def test_severity_filter_returns_only_matching(aid, atype, tgt, findings, sev):
    """get_findings(severity=X) returns only findings with that severity."""
    store = MemoryFindingPersistence()
    store.persist_analysis(aid, atype, tgt, findings)
    result = store.get_findings(severity=sev)
    for f in result:
        assert f["severity"] == sev


@given(
    analyses=st.lists(
        st.tuples(id_st, type_st, target_st, findings_st),
        min_size=0, max_size=10, unique_by=lambda t: t[0],
    ),
    limit=st.integers(min_value=0, max_value=20),
)
@settings(max_examples=50)
def test_list_analyses_limit_enforcement(analyses, limit):
    """list_analyses(limit=N) returns at most N items."""
    store = MemoryFindingPersistence()
    for aid, atype, tgt, findings in analyses:
        store.persist_analysis(aid, atype, tgt, findings)
    result = store.list_analyses(limit=limit)
    assert len(result) <= limit
    assert len(result) == min(len(analyses), limit)


@given(
    analyses=st.lists(
        st.tuples(id_st, type_st, target_st, findings_st),
        min_size=0, max_size=10, unique_by=lambda t: t[0],
    ),
)
@settings(max_examples=50)
def test_health_check_count_matches_persisted(analyses):
    """health_check()['count'] equals number of persisted analyses."""
    store = MemoryFindingPersistence()
    for aid, atype, tgt, findings in analyses:
        store.persist_analysis(aid, atype, tgt, findings)
    health = store.health_check()
    assert health["healthy"] is True
    assert health["backend"] == "memory"
    assert health["count"] == len(analyses)


# -- RuleBasedStateMachine stateful test --


class PersistenceStateMachine(RuleBasedStateMachine):
    """Stateful test: model dict stays in sync with MemoryFindingPersistence."""

    def __init__(self):
        super().__init__()
        self.store = None
        self.model: dict[str, dict] = {}

    @initialize()
    def init_store(self):
        self.store = MemoryFindingPersistence()
        self.model = {}

    @rule(aid=id_st, atype=type_st, tgt=target_st, findings=findings_st, summary=summary_st)
    def persist(self, aid, atype, tgt, findings, summary):
        res = self.store.persist_analysis(aid, atype, tgt, findings, summary)
        assert res["persisted"] is True
        self.model[aid] = {
            "analysis_id": aid, "analysis_type": atype, "target": tgt,
            "findings": findings, "summary": summary, "finding_count": len(findings),
        }

    @rule(aid=id_st)
    def get_analysis(self, aid):
        got = self.store.get_analysis(aid)
        if aid in self.model:
            assert got is not None
            assert got == self.model[aid]
        else:
            assert got is None

    @rule(limit=st.integers(min_value=0, max_value=30))
    def list_analyses(self, limit):
        result = self.store.list_analyses(limit=limit)
        assert len(result) <= limit
        assert len(result) == min(len(self.model), limit)

    @rule(sev=st.one_of(st.none(), severity_st), limit=st.integers(min_value=0, max_value=50))
    def get_findings(self, sev, limit):
        result = self.store.get_findings(severity=sev, limit=limit)
        # Build expected findings from model
        expected = []
        for rec in self.model.values():
            for f in rec["findings"]:
                if sev and f.get("severity") != sev:
                    continue
                expected.append({**f, "analysis_id": rec["analysis_id"]})
        assert len(result) <= limit
        assert len(result) == min(len(expected), limit)
        for f in result:
            if sev:
                assert f["severity"] == sev

    @invariant()
    def ids_in_sync(self):
        if self.store is not None:
            stored_ids = {a["analysis_id"] for a in self.store.list_analyses(limit=9999)}
            assert stored_ids == set(self.model.keys())

    @invariant()
    def health_count_matches(self):
        if self.store is not None:
            assert self.store.health_check()["count"] == len(self.model)


TestPersistenceStateful = PersistenceStateMachine.TestCase
TestPersistenceStateful.settings = settings(max_examples=50, stateful_step_count=20)
