"""Tests for blueprint spec normalizer — 3 shapes + edge cases."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.blueprint.runtime.normalizer import normalize_spec, _CFN_TYPE_MAP
from factory.blueprint.runtime.ports import NormalizedResource


# ── Fixtures ───────────────────────────────────────────────────────

FLAT_SPEC = {"service": "dynamodb", "construct": "Table", "props": {"table_name": "users"}}
CFN_SPEC = {
    "provider": "aws",
    "resources": [
        {"type": "AWS::DynamoDB::Table", "properties": {"table_name": "items"}},
        {"type": "AWS::S3::Bucket", "properties": {"bucket_name": "data"}},
    ],
}
LIST_SPEC = {
    "services": [
        {"service": "sns", "construct": "Topic", "props": {"topic_name": "alerts"}},
        {"service": "sqs", "construct": "Queue", "props": {}},
    ],
}


# ── Shape 1: Flat ──────────────────────────────────────────────────

class TestFlatShape:
    def test_returns_single_resource(self):
        result = normalize_spec("storage", FLAT_SPEC)
        assert len(result) == 1

    def test_service_and_construct(self):
        res = normalize_spec("storage", FLAT_SPEC)[0]
        assert res.service == "dynamodb"
        assert res.construct == "Table"

    def test_props_preserved(self):
        res = normalize_spec("storage", FLAT_SPEC)[0]
        assert res.props == {"table_name": "users"}

    def test_brick_name_set(self):
        res = normalize_spec("my-brick", FLAT_SPEC)[0]
        assert res.brick == "my-brick"

    def test_logical_id_generated(self):
        res = normalize_spec("storage", FLAT_SPEC)[0]
        assert res.logical_id != ""
        assert "Storage" in res.logical_id

    def test_flat_no_props(self):
        spec = {"service": "s3", "construct": "Bucket"}
        res = normalize_spec("store", spec)[0]
        assert res.props == {}


# ── Shape 2: CFN ───────────────────────────────────────────────────

class TestCfnShape:
    def test_returns_multiple_resources(self):
        result = normalize_spec("infra", CFN_SPEC)
        assert len(result) == 2

    def test_maps_cfn_types(self):
        result = normalize_spec("infra", CFN_SPEC)
        services = {r.service for r in result}
        assert services == {"dynamodb", "s3"}

    def test_unknown_cfn_type_skipped(self):
        spec = {"resources": [{"type": "AWS::Fake::Thing", "properties": {}}]}
        result = normalize_spec("x", spec)
        assert result == []

    def test_empty_resources_list(self):
        spec = {"resources": []}
        result = normalize_spec("x", spec)
        assert result == []

    def test_mixed_known_unknown(self):
        spec = {"resources": [
            {"type": "AWS::DynamoDB::Table", "properties": {}},
            {"type": "AWS::Fake::Nope", "properties": {}},
        ]}
        result = normalize_spec("x", spec)
        assert len(result) == 1

    def test_all_cfn_types_mapped(self):
        """Every entry in _CFN_TYPE_MAP should normalize successfully."""
        for cfn_type, (service, construct) in _CFN_TYPE_MAP.items():
            spec = {"resources": [{"type": cfn_type, "properties": {}}]}
            result = normalize_spec("test", spec)
            assert len(result) == 1, f"Failed for {cfn_type}"
            assert result[0].service == service


# ── Shape 3: List ──────────────────────────────────────────────────

class TestListShape:
    def test_returns_correct_count(self):
        result = normalize_spec("events", LIST_SPEC)
        assert len(result) == 2

    def test_services_match(self):
        result = normalize_spec("events", LIST_SPEC)
        assert result[0].service == "sns"
        assert result[1].service == "sqs"

    def test_empty_services_list(self):
        result = normalize_spec("x", {"services": []})
        assert result == []


# ── Edge Cases ─────────────────────────────────────────────────────

class TestEdgeCases:
    def test_empty_dict_returns_empty(self):
        assert normalize_spec("x", {}) == []

    def test_unrecognized_shape_returns_empty(self):
        assert normalize_spec("x", {"foo": "bar"}) == []

    def test_missing_construct_in_flat(self):
        """service without construct doesn't match flat shape."""
        assert normalize_spec("x", {"service": "s3"}) == []

    def test_logical_id_special_chars(self):
        res = normalize_spec("my-cool_brick", FLAT_SPEC)[0]
        assert " " not in res.logical_id
        assert "-" not in res.logical_id


# ── Hypothesis Property Tests ──────────────────────────────────────

_SERVICES = ["dynamodb", "s3", "sqs", "sns", "lambda", "kinesis"]
_CONSTRUCTS = ["Table", "Bucket", "Queue", "Topic", "Function", "Stream"]


@given(
    service=st.sampled_from(_SERVICES),
    construct=st.sampled_from(_CONSTRUCTS),
    brick=st.text(min_size=1, max_size=30, alphabet=st.characters(
        whitelist_categories=("L", "N"), whitelist_characters="-_",
    )),
)
@settings(max_examples=50)
def test_flat_shape_always_normalizes(service, construct, brick):
    """Any valid flat spec normalizes to exactly one resource."""
    spec = {"service": service, "construct": construct}
    result = normalize_spec(brick, spec)
    assert len(result) == 1
    assert result[0].service == service


@given(
    services=st.lists(
        st.fixed_dictionaries({
            "service": st.sampled_from(_SERVICES),
            "construct": st.sampled_from(_CONSTRUCTS),
        }),
        min_size=0, max_size=5,
    ),
)
@settings(max_examples=30)
def test_list_shape_count_matches(services):
    """List shape always returns same count as input services."""
    spec = {"services": services}
    result = normalize_spec("prop", spec)
    assert len(result) == len(services)
