"""Telemetry runtime - core runtime and deterministic surface."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

from .config import Settings, ExporterConfig, MetricDefinition, SCHEMA_VERSION
from .capabilities import capabilities_for
from factory.telemetry.runtime.metrics import MetricsSnapshot
from factory.telemetry.runtime.otel_setup import OTelRuntime
from factory.telemetry.runtime.registries import (
    ExporterRegistry,
    MetricRegistry,
    Registries,
    load_exporters,
    load_metric_definitions,
)
from factory.telemetry.runtime.init import read_settings_raw, initialize_otel, create_instruments
from .retention_runtime import RetentionRuntime
from .policy_config import compose_retention_days
from . import lifecycle
from .provenance_runtime import TelemetryProvenanceRuntime
from .provenance_store import JsonProvenanceStore
from .trace_operations import (
    extract_context as extract_trace_context,
    inject_context as inject_trace_context,
)


@dataclass
class TelemetryState:
    spans: dict[str, Any]
    snapshot: MetricsSnapshot


class TelemetryRuntime(RetentionRuntime):
    """Reusable telemetry runtime (no FastMCP imports)."""

    def __init__(self, config_dir: Path):
        self.config_dir = config_dir
        self.settings: Settings | None = None
        self.settings_raw: dict[str, Any] | None = None
        self.registries = Registries(
            metrics=MetricRegistry(definitions={}),
            exporters=ExporterRegistry(exporters={}),
        )
        self.provenance = TelemetryProvenanceRuntime(
            JsonProvenanceStore(config_dir / "provenance.sqlite3")
        )
        self.otel: OTelRuntime | None = None
        self._initialization_error: str | None = None
        self.state = TelemetryState(spans={}, snapshot=MetricsSnapshot())
        self._meter: Any | None = None
        self._tracer: Any | None = None
        self._logger: Any | None = None
        self._instruments: dict[str, Any] = {}
        self._propagator = TraceContextTextMapPropagator()

    # Instrument accessors for recording module
    @property
    def _counter_llm_tokens(self) -> Any:
        return self._instruments.get("counter_llm_tokens")

    @property
    def _hist_llm_latency_ms(self) -> Any:
        return self._instruments.get("hist_llm_latency_ms")

    @property
    def _counter_agent_exec(self) -> Any:
        return self._instruments.get("counter_agent_exec")

    @property
    def _counter_tool_invocations(self) -> Any:
        return self._instruments.get("counter_tool_invocations")

    def initialize(self) -> None:
        if self.otel is not None and self._initialization_error is None:
            return
        try:
            settings_raw = read_settings_raw(self.config_dir)
            settings = Settings.model_validate(settings_raw)
            registries = Registries(
                metrics=load_metric_definitions(self.config_dir),
                exporters=load_exporters(self.config_dir),
            )
            otel, tracer, meter, logger = initialize_otel(
                settings, registries, self.provenance,
            )
            instruments = create_instruments(meter)
        except Exception as exc:
            self._initialization_error = f"{type(exc).__name__}: {exc}"
            raise
        self.settings_raw = settings_raw
        self.settings = settings
        self.registries = registries
        self.otel = otel
        self._tracer = tracer
        self._meter = meter
        self._logger = logger
        self._instruments = instruments
        self._initialization_error = None

    def get_capabilities(self) -> dict[str, Any]:
        return capabilities_for(self.config_dir)

    def health_check(self) -> dict[str, Any]:
        return lifecycle.health(self)

    def get_collection_status(self) -> dict[str, Any]:
        """Report what telemetry collection actually does today (no per-owner opt-out)."""
        raw_days, rollup_days = compose_retention_days()
        policy = self.provenance.policy
        return {
            "collecting": True,
            "sample_rate": policy.sample_rate,
            "redacted_field_names": sorted(policy.redact_fields),
            "raw_retention_days": raw_days,
            "rollup_retention_days": rollup_days,
            "configurable": True,
        }

    def metrics_snapshot(self) -> dict[str, Any]:
        return self.state.snapshot.to_dict()

    def describe_config_schema(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "schemas": {
                "settings": Settings.model_json_schema(),
                "exporter": ExporterConfig.model_json_schema(),
                "metric_definition": MetricDefinition.model_json_schema(),
            },
        }

    # Provenance operations stay on the runtime; MCP only adapts flat DTOs.
    def ingest_provenance(self, batch: Any) -> Any:
        return self.provenance.ingest(batch)

    def read_provenance_reference(self, request: Any) -> Any:
        return self.provenance.read_reference(request)

    def materialize_provenance(self, request: Any) -> Any:
        return self.provenance.materialize(request)

    def activate_provenance_mapping(self, record: Any) -> Any:
        return self.provenance.activate_mapping(record)

    def inject_context(self) -> dict[str, Any]:
        return inject_trace_context(self._propagator)

    def extract_context(self, carrier: dict[str, str]) -> dict[str, Any]:
        return extract_trace_context(self._propagator, carrier)

    def flush_telemetry(self, timeout_ms: int = 5000) -> dict[str, Any]:
        return lifecycle.flush(self, timeout_ms)

    # Recording surface (delegated)
    def record_log(self, severity: Literal["DEBUG", "INFO", "WARN", "WARNING", "ERROR"],
                   body: str, attributes: dict[str, Any] | None,
                   trace_id: str | None = None, span_id: str | None = None) -> dict[str, Any]:
        from .recording import record_log
        return record_log(self, severity, body, attributes, trace_id, span_id)

    def record_llm_interaction(self, model: str, input_tokens: int, output_tokens: int,
                                latency_ms: float | None, cost_usd: float | None,
                                agent_id: str | None, workflow_id: str | None,
                                trace_attributes: dict[str, Any] | None) -> dict[str, Any]:
        from .recording import record_llm_interaction
        return record_llm_interaction(self, model, input_tokens, output_tokens, latency_ms,
                                       cost_usd, agent_id, workflow_id, trace_attributes)

    def record_agent_execution(self, agent_id: str, workflow_id: str, success: bool,
                                latency_ms: float | None, trace_attributes: dict[str, Any] | None) -> dict[str, Any]:
        from .recording import record_agent_execution
        return record_agent_execution(self, agent_id, workflow_id, success, latency_ms, trace_attributes)

    def record_tool_invocation(self, tool_name: str, workflow_id: str | None, success: bool,
                                latency_ms: float | None, trace_attributes: dict[str, Any] | None) -> dict[str, Any]:
        from .recording import record_tool_invocation
        return record_tool_invocation(self, tool_name, workflow_id, success, latency_ms, trace_attributes)

    def start_span(self, name: str, attributes: dict[str, Any] | None) -> dict[str, Any]:
        from .recording import start_span
        return start_span(self, name, attributes)

    def end_span(self, span_id: str, error: str | None) -> dict[str, Any]:
        from .recording import end_span
        return end_span(self, span_id, error)
