"""Strict local DTOs for the Test MCP boundary."""
from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


_INPUT_FIELDS: ContextVar[frozenset[str]] = ContextVar(
    "test_mcp_input_fields", default=frozenset()
)
_MAX_PATH = 512
_MAX_PATTERN = 256
_MAX_REPORT_ENTRIES = 100
_MAX_DIAGNOSTICS = 20

class StrictModel(BaseModel):
    """Reject unknown fields and coercion at the public boundary."""

    model_config = ConfigDict(extra="forbid", strict=True)

class StrictInputModel(StrictModel):
    """Capture explicitly supplied fields without changing the public DTO."""

    def model_post_init(self, __context: Any) -> None:
        _INPUT_FIELDS.set(frozenset(self.model_fields_set))


def supplied_input_fields() -> frozenset[str]:
    """Return fields supplied by the current strict MCP invocation."""
    return _INPUT_FIELDS.get()

class EmptyInput(StrictInputModel):
    """Input for tools without public arguments."""

class CapabilitiesFeatures(StrictModel):
    run_all_tests: bool
    run_component_tests: bool
    test_discovery: bool
    junit_debt_comparison: bool
    verbose_output: bool = True
    adapters: list[str]

class CapabilitiesOutput(StrictModel):
    name: str
    version: str
    description: str
    config_dir: str = ""
    adapter: str
    features: CapabilitiesFeatures

class HealthOutput(StrictModel):
    status: str
    backend: str = "unknown"
    version: str = "unknown"
    config_dir: str = ""
    error: str | None = None

class ConfigSchemaOutput(StrictModel):
    schema_definition: dict[str, Any]

class DiscoveryInput(StrictInputModel):
    path: str = Field(default=".", max_length=_MAX_PATH)
    pattern: str = Field(default="test_*.py", max_length=_MAX_PATTERN)

class DiscoveryOutput(StrictModel):
    target: str
    test_files: list[str] = Field(default_factory=list, max_length=_MAX_REPORT_ENTRIES)
    test_count: int
    errors: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    diagnostics: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    test_files_truncated: bool = False
    diagnostics_truncated: bool = False

class JunitCompareInput(StrictInputModel):
    base_report: str = Field(max_length=_MAX_PATH)
    candidate_report: str = Field(max_length=_MAX_PATH)

class JunitSummaryOutput(StrictModel):
    total: int = 0
    outcomes: dict[str, int] = Field(default_factory=dict, max_length=20)
    outcomes_truncated: bool = False

class JunitEntryOutput(StrictModel):
    identity: str = Field(max_length=4096)
    phase: str = Field(max_length=32)
    baseline_outcome: str = Field(max_length=32)
    candidate_outcome: str = Field(max_length=32)
    reason: str = Field(max_length=128)

class JunitCompareOutput(StrictModel):
    base_report: str
    candidate_report: str
    passed: bool
    base: JunitSummaryOutput = Field(default_factory=JunitSummaryOutput)
    candidate: JunitSummaryOutput = Field(default_factory=JunitSummaryOutput)
    blocking: list[JunitEntryOutput] = Field(
        default_factory=list, max_length=_MAX_REPORT_ENTRIES
    )
    legacy: list[JunitEntryOutput] = Field(
        default_factory=list, max_length=_MAX_REPORT_ENTRIES
    )
    resolved: list[JunitEntryOutput] = Field(
        default_factory=list, max_length=_MAX_REPORT_ENTRIES
    )
    errors: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    blocking_truncated: bool = False
    legacy_truncated: bool = False
    resolved_truncated: bool = False
    errors_truncated: bool = False
    regressions: int = 0
    resolved_count: int = 0
    unchanged: int = 0
    parse_errors: int = 0

class RunAllInput(StrictInputModel):
    verbose: bool = False

class ComponentRunInput(StrictInputModel):
    component_name: str = Field(max_length=64)
    verbose: bool = False

class PathRunInput(StrictInputModel):
    path: str = Field(max_length=_MAX_PATH)
    pattern: str = Field(default="test_*.py", max_length=_MAX_PATTERN)
    verbose: bool = False

class ExecutionOutput(StrictModel):
    execution_id: str
    target: str
    outcome: Literal[
        "passed", "failed", "timeout", "missing_target", "error", "invalid_target"
    ]
    success: bool = False
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    total: int = 0
    duration: float = 0.0
    output: str = ""
    output_truncated: bool = False
    errors: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    test_files: list[str] = Field(default_factory=list, max_length=_MAX_REPORT_ENTRIES)
    test_files_truncated: bool = False
    diagnostics: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    diagnostics_truncated: bool = False
    error: str | None = None
    component: str | None = None
    path: str | None = None

class ListFilesOutput(StrictModel):
    test_files: list[str] = Field(default_factory=list, max_length=_MAX_REPORT_ENTRIES)
    count: int
    errors: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    diagnostics: list[str] = Field(default_factory=list, max_length=_MAX_DIAGNOSTICS)
    test_files_truncated: bool = False
    diagnostics_truncated: bool = False

class AuthoringStatusOutput(StrictModel):
    enabled: bool
    config_dir: str = ""
    config_dir_exists: bool
    capabilities: list[str]
    adapter: str = ""
    pattern: str = "test_*.py"
    timeout_seconds: int = 300
    verbose: bool = False

class AdapterInput(StrictInputModel):
    adapter: str

class TimeoutInput(StrictInputModel):
    timeout_seconds: int

class PatternInput(StrictInputModel):
    pattern: str = Field(max_length=_MAX_PATTERN)

class VerboseInput(StrictInputModel):
    verbose: bool

class MutationOutput(StrictModel):
    success: bool
    error: str | None = None
    adapter: str | None = None
    timeout_seconds: int | None = None
    pattern: str | None = None
    verbose: bool | None = None
    message: str | None = None
