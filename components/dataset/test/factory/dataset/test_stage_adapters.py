"""Contract tests for the native generation stage adapters."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from factory.dataset.runtime.adapters.generation_stages import (
    APIGenMTStageAdapter,
    AgentInstructStageAdapter,
    ReviewInstructStageAdapter,
    S2MStageAdapter,
)
from factory.dataset.runtime.adapters.mock_completion import MockCompletionAdapter
from factory.dataset.runtime.adapters.stage_canary import verify_stage_contract
from factory.dataset.runtime.contracts import DatasetToolSchemaSnapshotRef


def _tool_schema_snapshot(tmp_path, allowed_tools: list[str]) -> DatasetToolSchemaSnapshotRef:
    content = json.dumps({"allowed_tools": allowed_tools}, sort_keys=True).encode()
    digest = hashlib.sha256(content).hexdigest()
    path = tmp_path / f"tool-schema-{digest}.json"
    if not path.exists():
        path.write_bytes(content)
        path.chmod(0o444)
    return DatasetToolSchemaSnapshotRef(uri=path.as_uri(), digest=digest, allowed_tools=allowed_tools)


def _temp_path(tmp_path: Path) -> Path:
    temp_dir = tmp_path / "dataset-stage-adapter"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir


@pytest.mark.parametrize(
    ("adapter_type", "config"),
    [
        (AgentInstructStageAdapter, {"k_variants": 2}),
        (S2MStageAdapter, {"min_turns": 4}),
        (APIGenMTStageAdapter, {"generate_responses": False}),
        (ReviewInstructStageAdapter, {"accept_threshold": 4.0}),
    ],
)
def test_stage_adapters_forward_records_and_supported_config(adapter_type, config, tmp_path: Path) -> None:
    calls = []
    output = {"messages": [{"role": "assistant", "content": "ok"}]}

    def fake_stage(records, **kwargs):
        calls.append((list(records), kwargs))
        return iter([output])

    adapter = adapter_type(fake_stage)
    expected_kwargs = config
    if adapter_type is APIGenMTStageAdapter:
        temp_path = _temp_path(tmp_path)
        config = {
            **config,
            "tool_schema_snapshot": _tool_schema_snapshot(temp_path, ["port_scan"]),
            "tools": [{"name": "port_scan", "description": "Scan ports", "parameters": {}}],
        }
        expected_kwargs = {
            key: value for key, value in config.items() if key != "tool_schema_snapshot"
        }

    result = list(adapter.execute([{"messages": [{"role": "user", "content": "input"}]}], config))

    assert result[0].model_dump(exclude_none=True) == output
    assert calls[0][0][0].model_dump(exclude_none=True) == {
        "messages": [{"role": "user", "content": "input"}]
    }
    assert calls[0][1] == expected_kwargs
    assert adapter.stage_version == "factory-native-1"


def test_stage_adapters_reject_unknown_configuration() -> None:
    adapter = S2MStageAdapter(lambda records, **kwargs: records)

    with pytest.raises(ValueError, match="Unsupported s2m configuration"):
        adapter.execute([], {"not_a_stage_option": True})


def test_stage_adapters_reject_pruned_legacy_configuration_keys() -> None:
    adapter = S2MStageAdapter(lambda records, **kwargs: records)

    for legacy_key in ("llm_config", "fallbacks", "timeout", "config"):
        with pytest.raises(ValueError, match="Unsupported s2m configuration"):
            adapter.execute([], {legacy_key: {"model": "x"}})


def test_stage_adapter_rejects_invalid_output() -> None:
    adapter = S2MStageAdapter(lambda records, **kwargs: [{"not": "a conversation"}])

    with pytest.raises(ValueError, match="Invalid conversation record at index 0"):
        list(adapter.execute([]))


def test_native_stage_canary() -> None:
    verify_stage_contract()


def test_stage_adapter_load_failure_is_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    adapter = AgentInstructStageAdapter()
    monkeypatch.setattr(
        "factory.dataset.runtime.adapters.generation_stages.import_module",
        lambda name: (_ for _ in ()).throw(ImportError("missing stage")),
    )

    with pytest.raises(RuntimeError, match="Native dataset stage is unavailable"):
        adapter.execute([])


def test_stage_adapter_resolves_backend_to_bound_completion() -> None:
    calls = []
    created = []

    def fake_stage(records, **kwargs):
        calls.append(kwargs)
        return iter([{"messages": [{"role": "assistant", "content": "ok"}]}])

    def completion_factory(**kwargs):
        completion = MockCompletionAdapter(model_id=f"{kwargs['backend']}/{kwargs.get('model', 'default')}")
        created.append((kwargs, completion))
        return completion

    adapter = S2MStageAdapter(fake_stage, completion_factory=completion_factory)

    list(adapter.execute([], {"min_turns": 3, "backend": "ollama", "model": "llama3.2", "temperature": 0.5}))

    assert created[0][0] == {"backend": "ollama", "model": "llama3.2", "temperature": 0.5}
    assert calls[0]["completion"] is created[0][1]
    assert calls[0]["min_turns"] == 3
    assert "backend" not in calls[0]
    assert "model" not in calls[0]


def test_stage_adapter_requires_factory_when_backend_is_present() -> None:
    adapter = S2MStageAdapter(lambda records, **kwargs: iter([]))

    with pytest.raises(ValueError, match="no completion factory is configured"):
        list(adapter.execute([], {"backend": "ollama"}))


def test_stage_adapter_rejects_raw_completion_in_recipe() -> None:
    adapter = S2MStageAdapter(
        lambda records, **kwargs: iter([]),
        completion_factory=lambda **kwargs: MockCompletionAdapter(),
    )

    with pytest.raises(ValueError, match="does not accept raw 'completion'"):
        list(adapter.execute([], {"backend": "ollama", "completion": MockCompletionAdapter()}))


def test_stage_adapter_surfaces_deterministic_fallback_record() -> None:
    adapter = S2MStageAdapter(lambda records, **kwargs: iter([]))

    list(adapter.execute([], {"use_llm": False}))
    assert adapter.fallback_record is not None
    assert adapter.fallback_record.actual_backend == "deterministic"
    assert adapter.fallback_record.authorized is True
    assert adapter.fallback_record.degraded_quality is True

    list(adapter.execute([], {"min_turns": 4}))
    assert adapter.fallback_record is None
