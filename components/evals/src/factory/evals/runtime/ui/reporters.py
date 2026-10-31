"""UI exploration reporters.

Report findings from UI exploration to various outputs:
- File (JSON/Markdown)
- Console
- GitHub Issues (via MCP)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Protocol
from pathlib import Path
import json


class FindingSeverity(str, Enum):
    """Severity levels for UI findings."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


@dataclass
class UIFinding:
    """A finding from UI exploration."""

    id: str
    scenario_id: str
    severity: FindingSeverity
    title: str
    description: str
    assertion_type: str
    route: str
    details: dict[str, Any] = field(default_factory=dict)
    screenshot_path: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "id": self.id,
            "scenario_id": self.scenario_id,
            "severity": self.severity.value,
            "title": self.title,
            "description": self.description,
            "assertion_type": self.assertion_type,
            "route": self.route,
            "details": self.details,
            "screenshot_path": self.screenshot_path,
            "timestamp": self.timestamp.isoformat(),
        }

    def to_markdown(self) -> str:
        """Convert to markdown format."""
        lines = [
            f"## {self.severity.value.upper()}: {self.title}",
            "",
            f"**Route:** `{self.route}`",
            f"**Scenario:** {self.scenario_id}",
            f"**Type:** {self.assertion_type}",
            "",
            self.description,
        ]
        if self.details:
            lines.extend(["", "### Details", "```json"])
            lines.append(json.dumps(self.details, indent=2))
            lines.append("```")
        return "\n".join(lines)


class UIReporter(Protocol):
    """Protocol for UI finding reporters."""

    def report(self, findings: list[UIFinding]) -> None:
        """Report findings."""
        ...

    def report_single(self, finding: UIFinding) -> None:
        """Report a single finding."""
        ...


@dataclass
class FileReporter:
    """Report findings to a file."""

    output_path: Path
    format: str = "json"  # json or markdown

    def report(self, findings: list[UIFinding]) -> None:
        """Write all findings to file."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        if self.format == "json":
            data = {
                "findings": [f.to_dict() for f in findings],
                "summary": self._summary(findings),
                "generated_at": datetime.now(timezone.utc).isoformat(),
            }
            self.output_path.write_text(json.dumps(data, indent=2))
        else:
            lines = ["# UI Exploration Findings", ""]
            lines.append(self._summary_markdown(findings))
            for finding in findings:
                lines.append(finding.to_markdown())
                lines.append("")
            self.output_path.write_text("\n".join(lines))

    def report_single(self, finding: UIFinding) -> None:
        """Append single finding to file."""
        # For single findings, just append
        if self.output_path.exists():
            existing = self.output_path.read_text()
        else:
            existing = ""

        if self.format == "markdown":
            self.output_path.write_text(existing + "\n" + finding.to_markdown())

    def _summary(self, findings: list[UIFinding]) -> dict[str, Any]:
        """Generate summary statistics."""
        by_severity = {}
        for f in findings:
            by_severity[f.severity.value] = by_severity.get(f.severity.value, 0) + 1
        return {
            "total": len(findings),
            "by_severity": by_severity,
        }

    def _summary_markdown(self, findings: list[UIFinding]) -> str:
        """Generate markdown summary."""
        summary = self._summary(findings)
        lines = [
            f"**Total Findings:** {summary['total']}",
            "",
            "| Severity | Count |",
            "|----------|-------|",
        ]
        for sev, count in summary["by_severity"].items():
            lines.append(f"| {sev} | {count} |")
        lines.append("")
        return "\n".join(lines)


@dataclass
class ConsoleReporter:
    """Report findings to console."""

    verbose: bool = False

    def report(self, findings: list[UIFinding]) -> None:
        """Print all findings."""
        print(f"\n{'='*60}")
        print(f"UI Exploration: {len(findings)} findings")
        print(f"{'='*60}\n")

        for finding in findings:
            self.report_single(finding)

    def report_single(self, finding: UIFinding) -> None:
        """Print single finding."""
        icon = {
            FindingSeverity.CRITICAL: "🔴",
            FindingSeverity.HIGH: "🟠",
            FindingSeverity.MEDIUM: "🟡",
            FindingSeverity.LOW: "🔵",
            FindingSeverity.INFO: "⚪",
        }.get(finding.severity, "⚪")

        print(f"{icon} [{finding.severity.value.upper()}] {finding.title}")
        print(f"   Route: {finding.route}")
        if self.verbose:
            print(f"   {finding.description}")
            if finding.details:
                print(f"   Details: {finding.details}")
        print()
