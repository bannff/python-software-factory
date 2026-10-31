"""Initialization logic for telemetry runtime."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from factory.telemetry.runtime.config import Settings
from factory.telemetry.runtime.otel_setup import OTelRuntime, configure_otel
from factory.telemetry.runtime.registries import Registries


def read_settings_raw(config_dir: Path) -> dict[str, Any]:
    """Read raw settings from YAML file."""
    path = config_dir / "settings.yaml"
    if not path.exists():
        raise ValueError(f"Missing settings.yaml in {config_dir}")
    data = yaml.safe_load(path.read_text())
    if not isinstance(data, dict):
        raise ValueError("settings.yaml must parse to a mapping")
    return data


def initialize_otel(
    settings: Settings,
    registries: Registries,
    provenance: Any = None,
) -> tuple[OTelRuntime, Any, Any, Any]:
    """Initialize OpenTelemetry runtime and instruments.
    
    Returns: (otel_runtime, tracer, meter, logger)
    """
    exporters = tuple(registries.exporters.exporters.values())
    otel = configure_otel(settings, exporters, provenance)
    tracer = otel.tracer_provider.get_tracer("telemetry-module")
    meter = otel.meter_provider.get_meter("telemetry-module")

    logger = None
    if otel.logger_provider:
        logger = otel.logger_provider.get_logger("telemetry-module")

    return otel, tracer, meter, logger


def create_instruments(meter: Any) -> dict[str, Any]:
    """Create standard OTEL instruments."""
    return {
        "counter_llm_tokens": meter.create_counter(
            "llm.tokens", description="Total LLM tokens", unit="1"
        ),
        "hist_llm_latency_ms": meter.create_histogram(
            "llm.latency_ms", description="LLM latency (ms)", unit="ms"
        ),
        "counter_agent_exec": meter.create_counter(
            "agent.executions", description="Agent executions", unit="1"
        ),
        "counter_tool_invocations": meter.create_counter(
            "tool.invocations", description="Tool invocations", unit="1"
        ),
    }
