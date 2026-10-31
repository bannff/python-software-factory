"""ScenarioPack publication, integrity, MCP, and root-isolation tests."""
from __future__ import annotations

import asyncio
import copy
from pathlib import Path

import pytest
from factory.mcp_utils.runtime.tool_catalog import ToolCatalog

from factory.dataset.interface import (
    dataset_get_scenario_pack, dataset_publish_scenario_pack,
)
from factory.dataset.mcp import deterministic, operational
from factory.dataset.runtime.scenario_errors import ScenarioPackIntegrityError
from factory.dataset.runtime.scenario_models import ScenarioPackDraft

from .scenario_fixtures import draft, draft_data


def _tool(mcp: ToolCatalog, name: str):
    return asyncio.run(mcp.get_tool(name)).fn


def test_publish_is_idempotent_and_conflict_is_typed(tmp_path: Path) -> None:
    first = dataset_publish_scenario_pack(draft(), tmp_path)
    second = dataset_publish_scenario_pack(draft(), tmp_path)
    assert first.status == "published"
    assert second.status == "existing"
    assert second.ref == first.ref
    changed = draft_data()
    changed["outcomes"][0]["definition"] = "Different"
    conflict = dataset_publish_scenario_pack(
        ScenarioPackDraft.model_validate(changed), tmp_path,
    )
    assert conflict.status == "conflict"
    assert conflict.ref is None
    assert conflict.conflict is not None
    assert conflict.conflict.existing_digest == first.ref.digest


def test_tamper_is_rejected_before_idempotency_or_conflict(tmp_path: Path) -> None:
    result = dataset_publish_scenario_pack(draft(), tmp_path)
    assert result.ref is not None
    artifact = Path(result.ref.uri.removeprefix("file://"))
    artifact.chmod(0o644)
    artifact.write_bytes(b"{}")
    with pytest.raises(ScenarioPackIntegrityError):
        dataset_publish_scenario_pack(draft(), tmp_path)


def test_out_of_root_and_wrong_root_fail_closed(tmp_path: Path) -> None:
    root = tmp_path / "one"
    result = dataset_publish_scenario_pack(draft(), root)
    assert result.ref is not None
    with pytest.raises(ScenarioPackIntegrityError, match="outside"):
        dataset_get_scenario_pack(
            result.ref.model_copy(update={"uri": (tmp_path / "outside.json").as_uri()}), root,
        )
    with pytest.raises(ScenarioPackIntegrityError):
        dataset_get_scenario_pack(result.ref, tmp_path / "two")


def test_flat_mcp_tools_honor_storage_root_and_categories(tmp_path: Path) -> None:
    mcp = ToolCatalog("scenario-pack-test")
    operational.register(mcp, tmp_path / "registered")
    deterministic.register(mcp, tmp_path / "registered")
    publish = _tool(mcp, "dataset_publish_scenario_pack")
    get = _tool(mcp, "dataset_get_scenario_pack")
    published = publish({
        "draft_json": draft().model_dump_json(), "storage_root": str(tmp_path / "override"),
    }).data.root
    ref = published["ref"]
    loaded = get({**ref, "storage_root": str(tmp_path / "override")}).data.root
    assert loaded["digest"] == ref["digest"]
    assert getattr(publish, "_mcp_category") == "operational"
    assert getattr(get, "_mcp_category") == "deterministic"


def test_dangling_claim_evidence_never_publishes(tmp_path: Path) -> None:
    data = copy.deepcopy(draft_data())
    data["claims"][0]["evidence_ids"] = ["missing"]
    with pytest.raises(ValueError, match="Dangling"):
        dataset_publish_scenario_pack(ScenarioPackDraft.model_validate(data), tmp_path)
    assert not list((tmp_path / "scenario_packs" / "sha256").glob("*.json"))
