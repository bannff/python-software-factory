"""Core types and constants for security component."""

from enum import Enum
from typing import Any

COMPONENT_NAME = "security"
COMPONENT_VERSION = "0.1.0"


class AnalysisType(str, Enum):
    """Types of security analysis."""
    THREAT_MODEL = "threat_model"
    CODE_ANALYSIS = "code_analysis"
    PEN_TEST = "pen_test"
    RECON = "recon"
    VULNERABILITY_SCAN = "vulnerability_scan"


class Severity(str, Enum):
    """Finding severity levels."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


DEFAULT_CONFIG: dict[str, Any] = {
    "max_findings": 100,
    "include_info": False,
    "timeout_seconds": 300,
}
