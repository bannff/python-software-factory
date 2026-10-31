"""Tests for blueprint resolver — VPC detection, IAM generation."""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from factory.blueprint.runtime.resolver import resolve
from factory.blueprint.runtime.ports import NormalizedResource, InfraBlueprint, IamStatement
from factory.blueprint.core import VPC_REQUIRED_SERVICES, SERVICE_IAM_ACTIONS


# ── Helpers ────────────────────────────────────────────────────────

def _make_resource(service: str, brick: str = "test") -> NormalizedResource:
    return NormalizedResource(
        brick=brick, service=service, construct="Thing",
        props={}, logical_id=f"{brick}{service}Thing",
    )


# ── Happy Path ─────────────────────────────────────────────────────

class TestResolveBasic:
    def test_empty_resources(self):
        bp = resolve([])
        assert bp.resources == []
        assert bp.shared_iam_statements == []
        assert bp.vpc_required is False
        assert bp.services_used == set()

    def test_single_resource(self):
        bp = resolve([_make_resource("dynamodb")])
        assert len(bp.resources) == 1
        assert "dynamodb" in bp.services_used

    def test_multiple_resources(self):
        resources = [_make_resource("dynamodb"), _make_resource("s3")]
        bp = resolve(resources)
        assert bp.services_used == {"dynamodb", "s3"}

    def test_duplicate_services_deduped(self):
        resources = [_make_resource("s3"), _make_resource("s3", brick="other")]
        bp = resolve(resources)
        assert bp.services_used == {"s3"}

    def test_resources_passed_through(self):
        resources = [_make_resource("sqs")]
        bp = resolve(resources)
        assert bp.resources is resources


# ── VPC Detection ──────────────────────────────────────────────────

class TestVpcDetection:
    def test_no_vpc_for_dynamodb(self):
        bp = resolve([_make_resource("dynamodb")])
        assert bp.vpc_required is False

    def test_vpc_for_neptune(self):
        bp = resolve([_make_resource("neptune")])
        assert bp.vpc_required is True

    def test_vpc_for_elasticache(self):
        bp = resolve([_make_resource("elasticache")])
        assert bp.vpc_required is True

    def test_vpc_for_aurora(self):
        bp = resolve([_make_resource("aurora-serverless")])
        assert bp.vpc_required is True

    def test_vpc_triggered_by_any_vpc_service(self):
        """Even one VPC service among many triggers vpc_required."""
        resources = [_make_resource("dynamodb"), _make_resource("neptune")]
        bp = resolve(resources)
        assert bp.vpc_required is True

    @pytest.mark.parametrize("service", sorted(VPC_REQUIRED_SERVICES))
    def test_all_vpc_services_detected(self, service):
        bp = resolve([_make_resource(service)])
        assert bp.vpc_required is True, f"{service} should require VPC"


# ── IAM Generation ─────────────────────────────────────────────────

class TestIamGeneration:
    def test_dynamodb_iam_actions(self):
        bp = resolve([_make_resource("dynamodb")])
        assert len(bp.shared_iam_statements) == 1
        stmt = bp.shared_iam_statements[0]
        assert stmt.effect == "Allow"
        assert "dynamodb:GetItem" in stmt.actions

    def test_no_iam_for_unknown_service(self):
        bp = resolve([_make_resource("unknown-svc")])
        assert bp.shared_iam_statements == []

    def test_iam_grouped_by_service(self):
        resources = [_make_resource("dynamodb"), _make_resource("s3")]
        bp = resolve(resources)
        assert len(bp.shared_iam_statements) == 2
        services_in_iam = [s.actions[0].split(":")[0] for s in bp.shared_iam_statements]
        assert "dynamodb" in services_in_iam
        assert "s3" in services_in_iam

    def test_iam_actions_sorted(self):
        bp = resolve([_make_resource("dynamodb")])
        actions = bp.shared_iam_statements[0].actions
        assert actions == sorted(actions)

    def test_iam_statements_sorted_by_service(self):
        resources = [_make_resource("sqs"), _make_resource("dynamodb")]
        bp = resolve(resources)
        services = [s.actions[0].split(":")[0] for s in bp.shared_iam_statements]
        assert services == sorted(services)

    def test_duplicate_service_no_duplicate_iam(self):
        resources = [_make_resource("s3"), _make_resource("s3", brick="b2")]
        bp = resolve(resources)
        assert len(bp.shared_iam_statements) == 1


# ── Hypothesis Property Tests ──────────────────────────────────────

_KNOWN_SERVICES = list(SERVICE_IAM_ACTIONS.keys())


@given(
    services=st.lists(
        st.sampled_from(_KNOWN_SERVICES), min_size=1, max_size=6,
    ),
)
@settings(max_examples=50)
def test_services_used_matches_input(services):
    """Resolved blueprint services_used always matches input services."""
    resources = [_make_resource(s) for s in services]
    bp = resolve(resources)
    assert bp.services_used == set(services)


@given(
    services=st.lists(
        st.sampled_from(_KNOWN_SERVICES), min_size=1, max_size=6,
    ),
)
@settings(max_examples=30)
def test_iam_count_le_unique_services(services):
    """IAM statement count never exceeds unique service count."""
    resources = [_make_resource(s) for s in services]
    bp = resolve(resources)
    assert len(bp.shared_iam_statements) <= len(set(services))
