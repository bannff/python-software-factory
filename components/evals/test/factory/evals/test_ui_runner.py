"""Tests for UI Explorer runner and reporters."""

import pytest
from pathlib import Path
import tempfile

from factory.evals.runtime.ui import (
    UIScenario,
    Fill,
    Click,
    ConsoleClean,
    NetworkOK,
    UIFinding,
    FindingSeverity,
    FileReporter,
    ConsoleReporter,
)
from factory.evals.runtime.adapters import UIExplorerRunner


class TestUIScenario:
    """Tests for UI scenarios."""

    def test_scenario_creation(self):
        """Create a scenario."""
        scenario = UIScenario(
            id="test-1",
            name="Login Test",
            route="/login",
            actions=[
                Fill("email", "test@example.com"),
                Click("submit"),
            ],
            assertions=[ConsoleClean()],
        )
        
        assert scenario.id == "test-1"
        assert len(scenario.actions) == 2
        assert len(scenario.assertions) == 1

    def test_scenario_to_dict(self):
        """Serialize scenario to dict."""
        scenario = UIScenario(
            id="test-1",
            name="Test",
            route="/test",
            tags=["smoke"],
        )
        data = scenario.to_dict()
        
        assert data["id"] == "test-1"
        assert data["route"] == "/test"
        assert "smoke" in data["tags"]


class TestUIExplorerRunner:
    """Tests for UI Explorer runner."""

    def test_create_scenario(self):
        """Create and retrieve scenario."""
        runner = UIExplorerRunner()
        scenario = UIScenario(id="s1", name="Test", route="/test")
        runner.create_scenario(scenario)
        
        retrieved = runner.get_scenario("s1")
        assert retrieved is not None
        assert retrieved.name == "Test"

    def test_list_scenarios(self):
        """List all scenarios."""
        runner = UIExplorerRunner()
        runner.create_scenario(UIScenario(id="s1", name="Test 1", route="/t1"))
        runner.create_scenario(UIScenario(id="s2", name="Test 2", route="/t2"))
        
        scenarios = runner.list_scenarios()
        assert len(scenarios) == 2

    def test_run_scenario(self):
        """Run scenario with context."""
        runner = UIExplorerRunner()
        scenario = UIScenario(
            id="s1",
            name="Test",
            route="/test",
            assertions=[ConsoleClean(), NetworkOK()],
        )
        runner.create_scenario(scenario)
        
        context = {
            "console_messages": [],
            "network_requests": [{"url": "/api", "status": 200}],
        }
        run = runner.run_scenario("s1", context)
        
        assert run.status == "completed"
        assert run.summary["passed"] == 2
        assert run.summary["failed"] == 0

    def test_run_scenario_with_failures(self):
        """Run scenario that has failures."""
        runner = UIExplorerRunner()
        scenario = UIScenario(
            id="s1",
            name="Test",
            route="/test",
            assertions=[ConsoleClean()],
        )
        runner.create_scenario(scenario)
        
        context = {
            "console_messages": [{"type": "error", "text": "Error!"}],
        }
        run = runner.run_scenario("s1", context)
        
        assert run.summary["failed"] == 1
        findings = runner.get_findings(run.id)
        assert len(findings) == 1

    def test_health_check(self):
        """Health check returns healthy."""
        runner = UIExplorerRunner()
        health = runner.health_check()
        
        assert health.healthy is True
        assert health.backend == "ui_explorer"


class TestUIReporters:
    """Tests for UI reporters."""

    def test_file_reporter_json(self):
        """File reporter writes JSON."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "findings.json"
            reporter = FileReporter(output_path=path, format="json")
            
            findings = [
                UIFinding(
                    id="f1",
                    scenario_id="s1",
                    severity=FindingSeverity.HIGH,
                    title="Console Error",
                    description="Found error",
                    assertion_type="console_clean",
                    route="/test",
                ),
            ]
            reporter.report(findings)
            
            assert path.exists()
            content = path.read_text()
            assert "Console Error" in content

    def test_file_reporter_markdown(self):
        """File reporter writes Markdown."""
        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "findings.md"
            reporter = FileReporter(output_path=path, format="markdown")
            
            findings = [
                UIFinding(
                    id="f1",
                    scenario_id="s1",
                    severity=FindingSeverity.MEDIUM,
                    title="A11y Issue",
                    description="Missing landmark",
                    assertion_type="a11y_valid",
                    route="/test",
                ),
            ]
            reporter.report(findings)
            
            assert path.exists()
            content = path.read_text()
            assert "## MEDIUM" in content

    def test_finding_to_markdown(self):
        """Finding converts to markdown."""
        finding = UIFinding(
            id="f1",
            scenario_id="s1",
            severity=FindingSeverity.HIGH,
            title="Test Finding",
            description="Test description",
            assertion_type="test",
            route="/test",
        )
        md = finding.to_markdown()
        
        assert "HIGH" in md
        assert "Test Finding" in md
        assert "/test" in md
