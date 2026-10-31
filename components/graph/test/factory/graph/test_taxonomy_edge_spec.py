"""Pydantic validation tests for ``TaxonomyEdgeSpec``.

Tracked under bd python-factory-ecph9 (epic python-factory-hadbi).
``model_config = ConfigDict(extra="forbid")`` rejects unknown fields,
and required fields are required.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings, strategies as st
from pydantic import ValidationError

from factory.graph.runtime.models import TaxonomyEdgeSpec


SETTINGS = settings(max_examples=50, deadline=None)


def test_extra_fields_forbidden() -> None:
    with pytest.raises(ValidationError):
        TaxonomyEdgeSpec.model_validate({
            "relationship_type": "X", "target_label": "Y",
            "target_props": {"a": "b"}, "extra_field": True,
        })


def test_required_fields_present() -> None:
    with pytest.raises(ValidationError):
        TaxonomyEdgeSpec.model_validate({
            "relationship_type": "X", "target_label": "Y",
            # target_props missing
        })


@given(
    rel=st.text(min_size=1, max_size=20,
                alphabet=st.characters(whitelist_categories=("L",))),
    label=st.text(min_size=1, max_size=20,
                  alphabet=st.characters(whitelist_categories=("L",))),
)
@SETTINGS
def test_round_trip_via_model_validate(rel: str, label: str) -> None:
    spec = TaxonomyEdgeSpec.model_validate({
        "relationship_type": rel, "target_label": label,
        "target_props": {"a": "col_a"},
    })
    assert spec.relationship_type == rel
    assert spec.target_label == label
    assert spec.target_props == {"a": "col_a"}
