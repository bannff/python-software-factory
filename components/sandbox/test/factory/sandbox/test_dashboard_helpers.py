"""Unit tests for the newly-extracted pure dashboard + event-payload helpers.

These cover the behavior-preserving refactor of ``dashboard_summary`` and
``runtime`` into focused sibling modules. They exercise the pure functions
directly (no runtime/invoker access required).
"""

from __future__ import annotations

from factory.sandbox.core import EnvironmentStatus
from factory.sandbox.mcp.dashboard_format import (
    adapter_name,
    age_label,
    age_minutes,
    health_state,
    sandbox_entity_id,
    status_rank,
)
from factory.sandbox.mcp.dashboard_graph import graph_rows_from_entity
from factory.sandbox.runtime.event_payloads import base_env_payload, lifecycle_payload
from factory.sandbox.runtime.models import EnvironmentInfo


def test_age_label_buckets() -> None:
    assert age_label(0) == "just now"
    assert age_label(5) == "5m"
    assert age_label(90) == "1h"
    assert age_label(60 * 24 * 3) == "3d"


def test_age_minutes_unparseable_is_zero() -> None:
    assert age_minutes("not-a-date") == 0


def test_health_state_mapping() -> None:
    assert health_state("running") == "healthy"
    assert health_state("provisioning") == "warming"
    assert health_state("terminated") == "inactive"
    assert health_state("error") == "error"
    assert health_state("weird") == "inactive"


def test_status_rank_orders_problems_first() -> None:
    assert status_rank("error") < status_rank("running")
    assert status_rank("running") < status_rank("terminated")
    assert status_rank("unlisted") == 99


def test_adapter_name_from_dict_and_scalar() -> None:
    assert adapter_name({"adapter": {"adapter": "docker"}}) == "docker"
    assert adapter_name({"adapter": "mock"}) == "mock"
    assert adapter_name({}) == "unknown"


def test_sandbox_entity_id_prefix() -> None:
    assert sandbox_entity_id("abc") == "sandbox-env-abc"


def test_graph_rows_dedupe_via_seen() -> None:
    seen: set[str] = set()
    entity = {"id": "e1", "type": "SandboxEnvironment", "properties": {"env_id": "x"}}
    first = graph_rows_from_entity(entity, focus_env_id="x", seen=seen)
    second = graph_rows_from_entity(entity, focus_env_id="x", seen=seen)
    assert len(first) == 1
    assert first[0]["label"] == "Sandbox Entity"
    assert second == []


def _env(env_id: str = "env-1") -> EnvironmentInfo:
    return EnvironmentInfo(
        env_id=env_id,
        status=EnvironmentStatus.RUNNING,
        instance_type="docker",
        created_at="2026-01-01T00:00:00+00:00",
        metadata={"run_id": "r1", "profile": "p1", "target_app": "app"},
    )


def test_base_env_payload_with_and_without_env() -> None:
    env = _env()
    with_env = base_env_payload("env-1", env)
    assert with_env == {
        "env_id": "env-1",
        "entity_id": "sandbox-env-env-1",
        "run_id": "r1",
        "profile": "p1",
        "target_app": "app",
    }
    without = base_env_payload("env-1", None)
    assert without["run_id"] is None
    assert without["profile"] is None
    assert without["target_app"] is None
    assert without["entity_id"] == "sandbox-env-env-1"


def test_lifecycle_payload_shape() -> None:
    payload = lifecycle_payload(_env())
    assert payload == {
        "env_id": "env-1",
        "entity_id": "sandbox-env-env-1",
        "status": "running",
        "instance_type": "docker",
        "profile": "p1",
        "run_id": "r1",
        "target_app": "app",
    }
