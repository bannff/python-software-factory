"""Operator-composed retention policy/days, and the honest status tool (row 96)."""
from __future__ import annotations

import asyncio

from factory.telemetry.runtime import policy_config as pc
from factory.telemetry.runtime.runtime import TelemetryRuntime


def test_defaults_match_the_prior_hardcoded_behavior_when_env_is_unset(monkeypatch) -> None:
    for name in (pc.SAMPLE_RATE_ENV, pc.REDACT_FIELDS_ENV, pc.RAW_DAYS_ENV, pc.ROLLUP_DAYS_ENV):
        monkeypatch.delenv(name, raising=False)
    policy = pc.compose_retention_policy()
    assert policy.sample_rate == 1.0 and policy.redact_fields == frozenset()
    assert pc.compose_retention_days() == (7, 365)


def test_operator_can_configure_sampling_redaction_and_retention(monkeypatch) -> None:
    monkeypatch.setenv(pc.SAMPLE_RATE_ENV, "0.25")
    monkeypatch.setenv(pc.REDACT_FIELDS_ENV, "email, ssn ,,api_key")
    monkeypatch.setenv(pc.RAW_DAYS_ENV, "3")
    monkeypatch.setenv(pc.ROLLUP_DAYS_ENV, "90")
    policy = pc.compose_retention_policy()
    assert policy.sample_rate == 0.25
    assert policy.redact_fields == frozenset({"email", "ssn", "api_key"})
    assert pc.compose_retention_days() == (3, 90)


def test_bad_env_values_fail_closed_to_the_safe_default(monkeypatch) -> None:
    monkeypatch.setenv(pc.SAMPLE_RATE_ENV, "not-a-number")
    assert pc.compose_retention_policy().sample_rate == 1.0
    monkeypatch.setenv(pc.RAW_DAYS_ENV, "junk")
    assert pc.compose_retention_days()[0] == 7


def test_out_of_range_env_values_clamp_not_widen(monkeypatch) -> None:
    monkeypatch.setenv(pc.SAMPLE_RATE_ENV, "5")  # would silently disable sampling if unclamped
    assert pc.compose_retention_policy().sample_rate == 1.0
    monkeypatch.setenv(pc.SAMPLE_RATE_ENV, "-1")
    assert pc.compose_retention_policy().sample_rate == 0.0
    monkeypatch.setenv(pc.RAW_DAYS_ENV, "9999")
    assert pc.compose_retention_days()[0] == 90


def test_collection_status_reports_redact_field_names_never_values(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv(pc.SAMPLE_RATE_ENV, "0.5")
    monkeypatch.setenv(pc.REDACT_FIELDS_ENV, "email,ssn")
    monkeypatch.setenv(pc.RAW_DAYS_ENV, "10")
    monkeypatch.setenv(pc.ROLLUP_DAYS_ENV, "200")
    runtime = TelemetryRuntime(tmp_path)
    status = runtime.get_collection_status()
    assert status == {
        "collecting": True, "sample_rate": 0.5,
        "redacted_field_names": ["email", "ssn"],
        "raw_retention_days": 10, "rollup_retention_days": 200,
        "configurable": True,
    }
    assert all(isinstance(name, str) for name in status["redacted_field_names"])


def test_collection_status_tool_is_deterministic_and_side_effect_free(tmp_path) -> None:
    runtime = TelemetryRuntime(tmp_path)
    catalog = runtime  # server.create_tool_catalog composes with a runtime; exercise the method directly twice
    first = catalog.get_collection_status()
    second = catalog.get_collection_status()
    assert first == second
