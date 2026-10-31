"""Property tests for metrics taxonomy extension.

Verifies: roundtrip, defaults, bounds, thresholds, taxonomy filtering, seed idempotency.
"""
from __future__ import annotations

from hypothesis import given, settings, strategies as st
from hypothesis.stateful import RuleBasedStateMachine, initialize, invariant, rule

from factory.metrics.core import MetricFormat, MetricType
from factory.metrics.runtime.adapters.memory import (
    InMemoryMetricsComputer, InMemoryMetricsStore,
)
from factory.metrics.runtime.models import MetricDefinition
from factory.metrics.runtime.runtime import MetricsRuntime

_alnum = st.characters(whitelist_categories=("L", "N"))
_ids = st.text(alphabet=_alnum, min_size=1, max_size=20)
_names = st.text(min_size=1, max_size=30)
_domains = st.sampled_from(["general", "platform", "infra", "quality"])
_categories = st.sampled_from(["uncategorized", "risk", "coverage", "performance"])
_tags = st.lists(st.sampled_from(["a", "b", "c", "d", "e"]), max_size=4, unique=True)
_formats = st.sampled_from([f.value for f in MetricFormat])
_metric_types = st.sampled_from(list(MetricType))
_input_tools = st.sampled_from(
    [None, "graph_query", "graph_get_recent_findings", "metrics_detect_drift"],
)

# ── MetricDefinition model properties ────────────────────────────

@given(mid=_ids, name=_names, domain=_domains,
       cat=_categories, fmt=_formats, tool=_input_tools)
@settings(max_examples=50)
def test_roundtrip_dump_validate(mid, name, domain, cat, fmt, tool):
    """Construct → model_dump → model_validate produces identical object."""
    defn = MetricDefinition(
        id=mid, name=name, domain=domain, category=cat,
        format=fmt, input_tool=tool,
    )
    raw = defn.model_dump(mode="json")
    restored = MetricDefinition.model_validate(raw)
    assert restored == defn


@given(mid=_ids, name=_names)
@settings(max_examples=50)
def test_default_taxonomy_values(mid, name):
    """Defaults: domain='general', category='uncategorized', format='number'."""
    defn = MetricDefinition(id=mid, name=name)
    assert defn.domain == "general"
    assert defn.category == "uncategorized"
    assert defn.format == "number"
    assert defn.source_brick is None
    assert defn.input_tool is None
    assert defn.bounds is None
    assert defn.thresholds == {}

@given(lo=st.floats(-1e6, 0, allow_nan=False), hi=st.floats(1, 1e6, allow_nan=False))
@settings(max_examples=50)
def test_bounds_tuple_accepted(lo, hi):
    """bounds=(lo, hi) round-trips through model_dump/validate."""
    defn = MetricDefinition(id="b", name="b", bounds=(lo, hi))
    raw = defn.model_dump(mode="json")
    assert raw["bounds"] == [lo, hi]
    restored = MetricDefinition.model_validate(raw)
    assert restored.bounds == (lo, hi)

@given(keys=st.lists(st.text(min_size=1, max_size=10), min_size=1, max_size=5, unique=True))
@settings(max_examples=50)
def test_thresholds_arbitrary_keys(keys):
    """thresholds dict accepts arbitrary string keys with float values."""
    th = {k: float(i) for i, k in enumerate(keys)}
    defn = MetricDefinition(id="t", name="t", thresholds=th)
    assert defn.thresholds == th

# ── Taxonomy filtering (RuleBasedStateMachine) ──────────────────

def _make_runtime() -> MetricsRuntime:
    return MetricsRuntime(InMemoryMetricsStore(), InMemoryMetricsComputer())


def _filter(rt, *, domain=None, category=None, source_brick=None,
            input_tool=None, tags=None):
    """Replicate metrics_get_by_taxonomy filtering logic."""
    results = []
    for d in rt.list_definitions():
        if domain and d.get("domain") != domain:
            continue
        if category and d.get("category") != category:
            continue
        if source_brick and d.get("source_brick") != source_brick:
            continue
        if input_tool and d.get("input_tool") != input_tool:
            continue
        if tags and not set(tags).issubset(set(d.get("tags", []))):
            continue
        results.append(d)
    return results


class TaxonomyFilterMachine(RuleBasedStateMachine):
    """Stateful test: register definitions, query by taxonomy filters."""

    def __init__(self):
        super().__init__()
        self.rt: MetricsRuntime | None = None
        self.model: dict[str, dict] = {}

    @initialize()
    def init(self):
        self.rt = _make_runtime()
        self.model = {}

    @rule(mid=_ids, name=_names, domain=_domains,
          cat=_categories, tags=_tags, mt=_metric_types, tool=_input_tools)
    def register(self, mid, name, domain, cat, tags, mt, tool):
        defn = MetricDefinition(
            id=mid, name=name, domain=domain, category=cat,
            tags=tags, metric_type=mt, source_brick="brick_" + domain,
            input_tool=tool,
        )
        self.rt.register_definition(defn)
        self.model[mid] = defn.model_dump(mode="json")

    @rule(domain=_domains)
    def query_by_domain(self, domain):
        results = _filter(self.rt, domain=domain)
        expected = [d for d in self.model.values() if d["domain"] == domain]
        assert len(results) == len(expected)

    @rule(cat=_categories)
    def query_by_category(self, cat):
        results = _filter(self.rt, category=cat)
        expected = [d for d in self.model.values() if d["category"] == cat]
        assert len(results) == len(expected)

    @rule(tags=_tags)
    def query_by_tags(self, tags):
        if not tags:
            return
        results = _filter(self.rt, tags=tags)
        expected = [d for d in self.model.values()
                    if set(tags).issubset(set(d.get("tags", [])))]
        assert len(results) == len(expected)

    @rule(domain=_domains, cat=_categories)
    def query_combined(self, domain, cat):
        results = _filter(self.rt, domain=domain, category=cat)
        expected = [d for d in self.model.values()
                    if d["domain"] == domain and d["category"] == cat]
        assert len(results) == len(expected)

    @rule(tool=_input_tools)
    def query_by_input_tool(self, tool):
        if tool is None:
            return
        results = _filter(self.rt, input_tool=tool)
        expected = [d for d in self.model.values()
                    if d.get("input_tool") == tool]
        assert len(results) == len(expected)

    @rule()
    def query_no_filters(self):
        results = _filter(self.rt)
        assert len(results) == len(self.model)

    @invariant()
    def count_matches(self):
        assert len(self.rt.list_definitions()) == len(self.model)


TestTaxonomyFilter = TaxonomyFilterMachine.TestCase
TestTaxonomyFilter.settings = settings(max_examples=50, stateful_step_count=15)

# ── Seed defaults idempotency ────────────────────────────────────

def test_seed_creates_then_skips():
    """First seed creates 8, second seed skips 8."""
    from factory.metrics.mcp.seed import _DEFAULT_DEFINITIONS
    rt = _make_runtime()
    created, skipped = [], []
    for raw in _DEFAULT_DEFINITIONS:
        defn = MetricDefinition(**raw)
        rt.register_definition(defn)
        created.append(raw["id"])
    assert len(created) == 8
    # Second pass — all should already exist
    skipped = [r["id"] for r in _DEFAULT_DEFINITIONS if rt.get_definition(r["id"])]
    assert len(skipped) == 8

def test_seeded_metrics_have_valid_taxonomy():
    """All 8 seeded metrics have non-empty domain, category, tags, and input_tool."""
    from factory.metrics.mcp.seed import _DEFAULT_DEFINITIONS
    for raw in _DEFAULT_DEFINITIONS:
        defn = MetricDefinition(**raw)
        assert defn.domain == "platform"
        assert defn.category in ("coverage", "risk", "performance", "quality")
        assert len(defn.tags) >= 1
        assert defn.source_brick is not None
        assert defn.input_tool is not None
