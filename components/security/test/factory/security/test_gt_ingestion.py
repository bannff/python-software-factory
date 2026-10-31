"""Property tests for factory.security.runtime.gt_ingestion.ingest_gt_entry.

Properties verified:
1. Result always contains keys: success, gt_id, kb_ingested, graph_nodes
2. gt_id in result matches gt_json["gt_id"]
3. graph_nodes["gt_entry"] is always 1 when gt_id is present
4. code_locations count matches len(gt_json["code_evidence"]["locations"])
5. endpoint is 1 when runtime_evidence.surface is present, 0 otherwise
6. commit is 1 when fix_evidence.fix_commit is non-empty, 0 otherwise
7. Minimal GT JSON (just gt_id) never crashes and returns success=True

All MCP calls are mocked via unittest.mock.patch on _invoke.
"""

from unittest.mock import patch

from hypothesis import given, settings
from hypothesis import strategies as st

from factory.security.runtime.gt_ingestion import ingest_gt_entry

# ---------------------------------------------------------------------------
# Strategies — printable ASCII only to avoid telemetry TinyDB side-effects
# ---------------------------------------------------------------------------

_ids = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)
_text = st.text(
    min_size=0, max_size=100,
    alphabet=st.characters(whitelist_categories=("L", "N", "P", "Z")),
)
_nonempty = st.text(
    min_size=1, max_size=40,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)

_location = st.fixed_dictionaries({
    "file": _text,
    "line_start": st.integers(min_value=0, max_value=9999),
    "line_end": st.integers(min_value=0, max_value=9999),
    "function": _text,
    "description": _text,
})

_surface = st.one_of(
    st.none(),
    st.fixed_dictionaries({
        "endpoint": _text,
        "method": st.sampled_from(["GET", "POST", "PUT", "DELETE"]),
    }),
)

_gt_json = st.fixed_dictionaries({
    "gt_id": _ids,
    "cwe": _text,
    "service_name": _text,
    "vulnerability_class": _text,
    "ground_truth": st.fixed_dictionaries({
        "statement": _text,
        "confidence": _text,
    }),
    "code_evidence": st.fixed_dictionaries({
        "locations": st.lists(_location, max_size=5),
    }),
    "runtime_evidence": st.fixed_dictionaries({"surface": _surface}),
    "fix_evidence": st.fixed_dictionaries({
        "fix_commit": st.one_of(st.just(""), _nonempty),
        "fix_cr": _text,
        "description": _text,
    }),
    "exploit_evidence": st.fixed_dictionaries({
        "reproduction_steps": st.lists(_text, max_size=3),
    }),
})

_MOCK_TARGET = "factory.security.runtime.gt_ingestion._invoke"
_CWE_MOCK = "factory.security.runtime.cwe_taxonomy._invoke"
_SETTINGS = settings(max_examples=50, deadline=None)


# ---------------------------------------------------------------------------
# Property 1 — result always has required keys
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_result_has_required_keys(gt):
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert isinstance(result, dict)
    for key in ("success", "gt_id", "kb_ingested", "graph_nodes"):
        assert key in result, f"Missing key: {key}"


# ---------------------------------------------------------------------------
# Property 2 — gt_id in result matches input
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_gt_id_matches_input(gt):
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert result["gt_id"] == gt["gt_id"]


# ---------------------------------------------------------------------------
# Property 3 — graph_nodes["gt_entry"] is always 1
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_gt_entry_node_always_one(gt):
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert result["graph_nodes"]["gt_entry"] == 1


# ---------------------------------------------------------------------------
# Property 4 — code_locations count matches input list length
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_code_locations_count_matches_input(gt):
    expected = len(gt.get("code_evidence", {}).get("locations", []))
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert result["graph_nodes"]["code_locations"] == expected


# ---------------------------------------------------------------------------
# Property 5 — endpoint is 1 iff runtime_evidence.surface is truthy
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_endpoint_presence_matches_surface(gt):
    surface = gt.get("runtime_evidence", {}).get("surface")
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert result["graph_nodes"]["endpoint"] == (1 if surface else 0)


# ---------------------------------------------------------------------------
# Property 6 — commit is 1 iff fix_commit is non-empty
# ---------------------------------------------------------------------------

@given(gt=_gt_json)
@_SETTINGS
def test_commit_presence_matches_fix_commit(gt):
    fix_commit = gt.get("fix_evidence", {}).get("fix_commit", "")
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry(gt)
    assert result["graph_nodes"]["commit"] == (1 if fix_commit else 0)


# ---------------------------------------------------------------------------
# Property 7 — minimal GT (just gt_id) never crashes, returns success=True
# ---------------------------------------------------------------------------

@given(gt_id=_ids)
@_SETTINGS
def test_minimal_gt_does_not_crash(gt_id):
    with patch(_MOCK_TARGET), patch(_CWE_MOCK):
        result = ingest_gt_entry({"gt_id": gt_id})
    assert result["success"] is True
    assert result["gt_id"] == gt_id
