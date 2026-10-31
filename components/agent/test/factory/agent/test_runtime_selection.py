"""Strict data-driven runtime selection tests."""

import pytest
from pydantic import ValidationError

from factory.agent.runtime.runtime_selection import (
    AgentRuntimeConfigError,
    load_runtime_selection,
)


def test_loads_project_runtime_adapter_yaml(tmp_path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text(
        "schema_version: v1\nruntime_adapter_id: langchain-langgraph\noptions: {}\n",
        encoding="utf-8",
    )
    selection = load_runtime_selection(path)
    assert selection.runtime_adapter_id == "langchain-langgraph"


def test_rejects_unknown_configuration_fields(tmp_path) -> None:
    path = tmp_path / "runtime.yaml"
    path.write_text(
        "schema_version: v1\nruntime_adapter_id: test\nframework_class: bad\n",
        encoding="utf-8",
    )
    with pytest.raises(ValidationError):
        load_runtime_selection(path)


def test_missing_configured_file_raises_actionable_error(monkeypatch, tmp_path) -> None:
    missing = tmp_path / "config" / "agent-runtime.yaml"
    monkeypatch.setenv("AGENT_RUNTIME_CONFIG", str(missing))

    with pytest.raises(AgentRuntimeConfigError) as raised:
        load_runtime_selection()

    message = str(raised.value)
    assert "AGENT_RUNTIME_CONFIG" in message
    assert str(missing) in message


def test_unset_config_falls_back_to_the_builtin_adapter(monkeypatch) -> None:
    monkeypatch.delenv("AGENT_RUNTIME_CONFIG", raising=False)
    monkeypatch.delenv("AGENT_RUNTIME_ADAPTER", raising=False)

    assert load_runtime_selection().runtime_adapter_id == "strands"
