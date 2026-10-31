"""QA edge-case property tests for the graph_id<->workflow_id alias layer.

bd python-factory-col2 (qa-tester pass). The four canonical invariants live
in ``test_alias_compat.py``; this file pins additional QA-discovered edges:

  * empty-default skip path: validator must NOT raise when both keys are
    absent or both default to empty strings (the model returns ('', '')).
  * unicode round-trip: validator must preserve characters from arbitrary
    Unicode categories L/N including surrogate-pair-free emoji.
  * long-identifier round-trip: 256-char ids must survive both backfill
    directions intact.
  * subclass inheritance: ``RewardComputedPayload`` exercises the same
    pre-validator (no override, no reordering hazard).
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.events.runtime.learning_contracts import (
    LearningEventPayload,
    RewardComputedPayload,
)

# Unicode strategy: any letter/number across scripts, broader than the core
# test file's L+N+dash+underscore set. Excludes surrogate halves explicitly.
_unicode_id = st.text(
    min_size=1, max_size=64,
    alphabet=st.characters(whitelist_categories=("L", "N", "S")),
)
_long_id = st.text(
    min_size=64, max_size=256,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


def test_empty_defaults_skip_validator():
    """Both keys absent — model defaults to ('', ''), validator skips silently."""
    out = LearningEventPayload(run_id="r", workflow_run_id="wf").model_dump()
    assert out["graph_id"] == ""
    assert out["workflow_id"] == ""


def test_explicit_empty_strings_skip_validator():
    """Explicit '' for both — validator's truthy guard short-circuits, no raise."""
    out = LearningEventPayload(
        run_id="r", workflow_run_id="wf", graph_id="", workflow_id="",
    ).model_dump()
    assert out["graph_id"] == out["workflow_id"] == ""


@settings(max_examples=60)
@given(ident=_unicode_id)
def test_unicode_graph_id_roundtrips_via_alias(ident):
    """Unicode L/N/S code points survive graph_id->workflow_id backfill."""
    out = LearningEventPayload(
        run_id="r", workflow_run_id="wf", graph_id=ident,
    ).model_dump()
    assert out["graph_id"] == out["workflow_id"] == ident


@settings(max_examples=60)
@given(ident=_unicode_id)
def test_unicode_workflow_id_roundtrips_via_alias(ident):
    """Same invariant in the workflow_id-only direction."""
    out = LearningEventPayload(
        run_id="r", workflow_run_id="wf", workflow_id=ident,
    ).model_dump()
    assert out["graph_id"] == out["workflow_id"] == ident


@settings(max_examples=40)
@given(ident=_long_id)
def test_long_identifiers_roundtrip(ident):
    """Long (64-256 char) identifiers do not get truncated by either branch."""
    fwd = LearningEventPayload(
        run_id="r", workflow_run_id="wf", graph_id=ident,
    ).model_dump()
    rev = LearningEventPayload(
        run_id="r", workflow_run_id="wf", workflow_id=ident,
    ).model_dump()
    assert fwd["workflow_id"] == ident
    assert rev["graph_id"] == ident


def test_reward_subclass_inherits_normalize_validator():
    """RewardComputedPayload subclass must run the parent's pre-validator."""
    from_graph = RewardComputedPayload(
        run_id="r", workflow_run_id="wf", idempotency_key="k",
        graph_id="rt-sast-scan",
    ).model_dump()
    assert from_graph["graph_id"] == from_graph["workflow_id"] == "rt-sast-scan"
    from_workflow = RewardComputedPayload(
        run_id="r", workflow_run_id="wf", idempotency_key="k",
        workflow_id="rt-sast-scan",
    ).model_dump()
    assert from_workflow["graph_id"] == from_workflow["workflow_id"] == "rt-sast-scan"
    with pytest.raises(ValidationError):
        RewardComputedPayload(
            run_id="r", workflow_run_id="wf", idempotency_key="k",
            graph_id="A", workflow_id="B",
        )


def test_one_side_empty_is_treated_as_absent():
    """graph_id='', workflow_id='x' — empty side is falsy, NOT a mismatch."""
    out = LearningEventPayload(
        run_id="r", workflow_run_id="wf", graph_id="", workflow_id="x",
    ).model_dump()
    assert out["graph_id"] == out["workflow_id"] == "x"
    out2 = LearningEventPayload(
        run_id="r", workflow_run_id="wf", graph_id="y", workflow_id="",
    ).model_dump()
    assert out2["graph_id"] == out2["workflow_id"] == "y"
