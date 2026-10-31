"""Typed ModelPassport MCP authority surface."""
from __future__ import annotations

import asyncio
import inspect
from pathlib import Path

import pytest

from factory.machine_learning.runtime.adapters.model_passport_store import (
    LocalModelPassportStore,
)
from factory.machine_learning.server import create_mcp_server
from factory.mcp_utils.interface import get_service, set_service

from .passport_fixtures import passport, passport_invoker


@pytest.fixture(autouse=True)
def restore_invoker():
    previous = get_service("tool_invoker")
    yield
    set_service("tool_invoker", previous)


def test_public_surface_has_no_publish_or_caller_root_arguments(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    value = passport(tmp_path)
    set_service("tool_invoker", passport_invoker(value))
    monkeypatch.setenv("ML_MODEL_PASSPORT_ROOT", str(tmp_path))
    ref = LocalModelPassportStore(tmp_path).publish(value).ref
    server = create_mcp_server()
    tools = {tool.name for tool in asyncio.run(server.list_tools())}
    assert "ml_publish_model_passport" not in tools

    exact = asyncio.run(server.get_tool("ml_get_model_passport"))
    by_model = asyncio.run(server.get_tool("ml_get_model_passport_by_model"))
    promote = asyncio.run(server.get_tool("ml_verify_and_promote_lightgbm_passport"))
    promote_can = asyncio.run(server.get_tool("ml_verify_and_promote_can_passport"))
    for tool in (exact, by_model, promote, promote_can):
        parameters = inspect.signature(tool.fn).parameters
        assert "storage_root" not in parameters
        assert "passport_storage_root" not in parameters

    result = exact.fn(
        model_id=ref.model_id, model_version=ref.model_version,
        passport_revision=ref.passport_revision, passport_uri=ref.uri,
        passport_digest=ref.digest,
    )
    assert result.ok and result.data is not None
    assert result.data.passport_digest == value.passport_digest
    by_model_result = by_model.fn(
        model_id=ref.model_id, model_version=ref.model_version,
        passport_revision=ref.passport_revision,
    )
    assert by_model_result.ok and by_model_result.data == result.data


def test_passport_tools_publish_strict_models_and_failed_envelopes(tmp_path: Path) -> None:
    server = create_mcp_server()
    tool = asyncio.run(server.get_tool("ml_get_model_passport"))
    assert tool.fn._mcp_input_model.model_config["extra"] == "forbid"
    assert tool.fn._mcp_output_model.__name__ == "PassportOutput"
    with pytest.raises(Exception):
        tool.fn(
            model_id="m", model_version="1", passport_revision=1,
            passport_uri="file:///missing", passport_digest="0" * 64,
            unknown=True,
        )
    result = tool.fn(
        model_id="m", model_version="1", passport_revision=1,
        passport_uri="file:///missing", passport_digest="0" * 64,
    )
    assert not result.ok and result.data is None and result.error
    model_info = asyncio.run(server.get_tool("can_get_model_info"))
    missing = model_info.fn(model_id="missing")
    assert missing.ok and missing.data is not None and not missing.data.found
    with pytest.raises(Exception):
        model_info.fn(model_id="missing", unknown=True)
