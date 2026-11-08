"""Invalid upsert input surfaces a typed reason, not opaque tool_execution_failed (#342)."""
from __future__ import annotations

from pathlib import Path

import pytest
from factory.workflow.authoring import AuthoringManager
from factory.workflow.mcp.authoring import register

_STEP = {"id": "s1", "kind": "noop"}
_TOOL = "workflow.authoring.upsert_workflow_definition"


class _Registry:
    """Captures tool functions the way ``mcp.tool(name=...)`` would register them."""

    def __init__(self) -> None:
        self.tools: dict = {}

    def tool(self, name: str):
        def deco(fn):
            self.tools[name] = fn
            return fn
        return deco


@pytest.fixture
def upsert(tmp_path: Path):
    registry = _Registry()
    runtime = type("Runtime", (), {"config_dir": tmp_path, "reload_workflows": lambda self: None})()
    register(registry, runtime, AuthoringManager(config_dir=tmp_path))
    return registry.tools[_TOOL]


@pytest.mark.parametrize(
    ("kwargs", "expected"),
    [
        ({"id": "Bad ID", "yaml_or_object": {"name": "x", "version": 1, "steps": [_STEP]}},
         "workflow_id_invalid"),
        ({"id": "ok", "yaml_or_object": "steps: [unclosed"}, "workflow_yaml_invalid"),
        ({"id": "ok", "yaml_or_object": {"name": "x", "version": 1, "steps": []}},
         "workflow_definition_invalid:steps"),
    ],
)
def test_invalid_definition_returns_typed_reason(upsert, kwargs, expected) -> None:
    result = upsert(**kwargs)
    assert result.ok is False
    assert result.error == expected


def test_valid_definition_still_succeeds(upsert) -> None:
    result = upsert(id="ok", yaml_or_object={"name": "x", "version": 1, "steps": [_STEP]})
    assert result.ok is True
