"""Tests for default OTEL env injected into sandbox provisions."""
from __future__ import annotations

import pytest

from factory.sandbox.runtime.observability import default_otel_env


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for key in (
        "SANDBOX_OTEL_ENABLED", "SANDBOX_OTEL_ENDPOINT",
        "OTEL_EXPORTER_OTLP_ENDPOINT", "SANDBOX_OTEL_PROTOCOL",
    ):
        monkeypatch.delenv(key, raising=False)


def test_no_endpoint_yields_empty(monkeypatch):
    # No collector configured → inject nothing (avoid half-set OTEL config).
    assert default_otel_env("env-1", "rust-sdk") == {}


def test_endpoint_populates_standard_vars(monkeypatch):
    monkeypatch.setenv("SANDBOX_OTEL_ENDPOINT", "http://companionx:4318")
    env = default_otel_env("env-1", "rust-sdk")
    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://companionx:4318"
    assert env["OTEL_SERVICE_NAME"] == "sandbox-rust-sdk"
    assert "sandbox.env_id=env-1" in env["OTEL_RESOURCE_ATTRIBUTES"]
    assert "sandbox.profile=rust-sdk" in env["OTEL_RESOURCE_ATTRIBUTES"]
    assert env["OTEL_TRACES_EXPORTER"] == "otlp"


def test_falls_back_to_standard_otel_endpoint(monkeypatch):
    monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://collector:4318")
    env = default_otel_env("env-2", None)
    assert env["OTEL_EXPORTER_OTLP_ENDPOINT"] == "http://collector:4318"
    assert env["OTEL_SERVICE_NAME"] == "sandbox"
    assert "sandbox.profile=ad_hoc" in env["OTEL_RESOURCE_ATTRIBUTES"]


def test_disabled_yields_empty(monkeypatch):
    monkeypatch.setenv("SANDBOX_OTEL_ENDPOINT", "http://companionx:4318")
    monkeypatch.setenv("SANDBOX_OTEL_ENABLED", "0")
    assert default_otel_env("env-1", "rust-sdk") == {}


def test_optional_protocol(monkeypatch):
    monkeypatch.setenv("SANDBOX_OTEL_ENDPOINT", "http://c:4318")
    monkeypatch.setenv("SANDBOX_OTEL_PROTOCOL", "http/protobuf")
    env = default_otel_env("e", "p")
    assert env["OTEL_EXPORTER_OTLP_PROTOCOL"] == "http/protobuf"
