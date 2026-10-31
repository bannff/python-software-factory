"""Memory migration import subtype, tag, and strict-contract tests."""
from __future__ import annotations

import pytest

from factory.memory.mcp.contracts.migration_import import MemoryImportInput
from .test_migration_import_tool import (
    _args, _dispatch, invoker, runtime, tool,
)

def test_subtype_maps_to_memory_type(runtime, tool, invoker) -> None:
    semantic = _dispatch(tool, _args(subtype="semantic", source_record_id="1" * 64, key="k1"))
    episodic = _dispatch(tool, _args(subtype="episodic", source_record_id="2" * 64, key=""))
    assert runtime.get(semantic.data.memory_id).memory_type == "long_term"
    assert runtime.get(episodic.data.memory_id).memory_type == "episodic"


def test_tags_preserved_and_filterable(runtime, tool, invoker) -> None:
    memory = runtime.get(_dispatch(tool, _args(tags=["team", "ops"])).data.memory_id)
    assert memory.metadata["tags"] == ["team", "ops"]
    hit = runtime.retrieve(user_id=memory.user_id, query="durable", min_relevance=0.0, tags=["ops"])
    assert any(m.id == memory.id for m in hit)
    miss = runtime.retrieve(user_id=memory.user_id, query="durable", min_relevance=0.0, tags=["absent"])
    assert all(m.id != memory.id for m in miss)


def test_input_forbids_unknown_fields_and_requires_all(runtime) -> None:
    valid = _args()
    MemoryImportInput.model_validate(valid)  # exact field set validates
    with pytest.raises(Exception):
        MemoryImportInput.model_validate({**valid, "unexpected": True})
    with pytest.raises(Exception):
        MemoryImportInput.model_validate({k: v for k, v in valid.items() if k != "owner_id"})
