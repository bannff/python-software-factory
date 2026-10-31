"""Module-level workflow contract surfaces delegate to the runtime."""
import logging
from unittest.mock import MagicMock

import pytest

from factory.workflow import server
from factory.workflow.runtime.operations import WorkflowError


def test_module_surfaces_delegate_without_false_backend_claims(monkeypatch):
    runtime = MagicMock()
    runtime.get_capabilities.return_value = {
        "feature_flags": {"durable_named_mcp_execution": "sqlite-only"},
    }
    runtime.health_check.return_value = {
        "status": "ok", "storage": {"backend": "sqlite"},
        "durable_named_mcp_ready": True,
    }
    runtime.describe_config_schema.return_value = {"settings_schema": {}}
    monkeypatch.setattr(server, "get_runtime", lambda: runtime)

    capabilities = server.get_capabilities()
    health = server.health_check()
    assert capabilities["feature_flags"]["durable_named_mcp_execution"] == "sqlite-only"
    assert health["storage"]["backend"] == "sqlite"
    assert server.describe_config_schema() == {"settings_schema": {}}
    runtime.get_capabilities.assert_called_once_with()
    runtime.health_check.assert_called_once_with()


def test_explicit_config_dir_without_settings_yaml_fails_fast(monkeypatch, tmp_path):
    """An operator-asserted config dir must never degrade into an empty registry.

    Continuing anyway would surface much later as ``unknown execution engine:
    <id>`` from an unrelated code path (issue #34), so this raises and the
    message names the env var, the missing path and the shipped template.
    """
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    template = config_dir / "settings.yaml.example"
    template.write_text("service:\n  name: template\n")
    monkeypatch.setenv("WORKFLOW_CONFIG_DIR", str(config_dir))

    with pytest.raises(WorkflowError) as excinfo:
        server.get_runtime()

    message = str(excinfo.value)
    assert "WORKFLOW_CONFIG_DIR" in message
    assert str(config_dir) in message
    assert str((config_dir / "settings.yaml").resolve()) in message
    assert str(template.resolve()) in message


def test_fail_fast_message_names_the_template_when_it_is_not_beside_the_config(
    monkeypatch, tmp_path,
):
    config_dir = tmp_path / "config"
    monkeypatch.setenv("WORKFLOW_CONFIG_DIR", str(config_dir))

    with pytest.raises(WorkflowError) as excinfo:
        server.get_runtime()

    assert "settings.yaml.example" in str(excinfo.value)


def test_explicit_config_dir_provenance_reports_the_real_failure_mode(
    monkeypatch, tmp_path,
):
    """The provenance surface must describe the actual observable behaviour."""
    config_dir = tmp_path / "config"
    monkeypatch.setenv("WORKFLOW_CONFIG_DIR", str(config_dir))

    provenance = server._config_provenance()

    assert provenance["configured"] is False
    assert provenance["missing"] == str((config_dir / "settings.yaml").resolve())
    assert "raises WorkflowError" in provenance["reason"]
    assert "unhealthy with zero workflow tools" in provenance["reason"]


def test_unset_config_dir_logs_actionable_warning_and_starts_degraded(
    monkeypatch, tmp_path, caplog,
):
    """The library default (./config) may legitimately be absent — still loud."""
    monkeypatch.delenv("WORKFLOW_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    expected_missing = str((tmp_path / "config" / "settings.yaml").resolve())

    with caplog.at_level(logging.WARNING):
        runtime = server.get_runtime()

    assert runtime.executor.backend_name == "local"
    assert runtime.storage.health_check()["ok"] is True
    assert runtime.execution_engines.capabilities() == []
    warnings = [
        record.getMessage()
        for record in caplog.records
        if record.levelno == logging.WARNING
    ]
    assert any(
        "WORKFLOW_CONFIG_DIR is unset" in message and expected_missing in message
        for message in warnings
    ), warnings
    assert any("settings.yaml.example" in message for message in warnings), warnings


def test_unconfigured_config_dir_is_reported_in_module_surfaces(
    monkeypatch, tmp_path, caplog,
):
    monkeypatch.delenv("WORKFLOW_CONFIG_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    expected_missing = str((tmp_path / "config" / "settings.yaml").resolve())

    with caplog.at_level(logging.WARNING):
        health = server.health_check()
        capabilities = server.get_capabilities()

    assert health["config"]["configured"] is False
    assert health["config"]["missing"] == expected_missing
    assert capabilities["config"]["configured"] is False
    assert capabilities["config"]["missing"] == expected_missing
    assert "empty execution-engine registry" in health["config"]["reason"]
