"""Typed CAN family-config preflight must precede every Dataset stage."""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from factory.machine_learning.interface import (
    PassportArtifactRef, TrackingRuntime, create_server, run_keystone_pipeline,
)
from factory.machine_learning.runtime.adapters.chronos_identity import MODEL_REVISION


def _runtime(root: Path) -> TrackingRuntime:
    return TrackingRuntime({"model_passport_root": str(root)})


def _fake_ref(root: Path) -> dict[str, object]:
    digest = "a" * 64
    return PassportArtifactRef(
        role="backbone",
        uri=(root / "backbones" / "chronos-2" / digest).as_uri(),
        digest=digest,
        media_type="application/vnd.amazon.chronos2.backbone",
        format="chronos2-backbone",
        size_bytes=1,
        identity="amazon/chronos-2",
        version=MODEL_REVISION,
    ).model_dump(mode="json")


def _run(root: Path, model_types: list[str], model_configs: dict) -> dict:
    with patch(
        "factory.machine_learning.runtime.can_keystone.run_keystone_stage",
        side_effect=AssertionError("Dataset stage ran before config preflight"),
    ):
        return run_keystone_pipeline(
            mf4_dir="unused", dbc_path="unused", runtime=_runtime(root),
            model_types=model_types, model_configs=model_configs,
        )


def test_public_model_configs_schema_is_closed_and_discoverable() -> None:
    tool = asyncio.run(create_server(TrackingRuntime()).get_tool("can_run_full_pipeline"))
    schema = tool.fn._mcp_input_model.model_json_schema(mode="validation")
    branch = next(
        item for item in schema["properties"]["model_configs"]["anyOf"]
        if "$ref" in item
    )
    config_schema = schema["$defs"][branch["$ref"].rsplit("/", 1)[-1]]
    assert config_schema["additionalProperties"] is False
    assert set(config_schema["properties"]) == {
        "lightgbm", "lstm", "tcn", "patchtst", "chronos", "lnn",
    }
    assert not any(
        item.get("additionalProperties") is True
        for item in schema["properties"]["model_configs"]["anyOf"]
    )


def test_public_model_configs_forwards_dumped_mapping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, Any] = {}

    def run_pipeline(**kwargs: Any) -> dict[str, Any]:
        seen.update(kwargs)
        return {
            "vehicle_id": "unknown", "ingest": {}, "profile": {},
            "contract_artifacts": {}, "synthesize": {}, "window": {}, "augment": {},
            "top_can_ids": [], "comparison_table": [], "model_ids": [],
            "warm_model_ids": [], "inference_gate": {},
        }

    monkeypatch.setattr(
        "factory.machine_learning.mcp.can_pipeline_tool.run_keystone_pipeline",
        run_pipeline,
    )
    server = create_server(TrackingRuntime())
    tool_result = asyncio.run(server.call_tool("can_run_full_pipeline", {
        "mf4_dir": "unused-mf4", "dbc_path": "unused-dbc",
        "model_types": ["lnn"],
        "model_configs": {
            "lnn": {"auxiliary_uris": {"timespans": "file:///times.npy"}},
        },
    }))
    assert tool_result.structured_content["ok"] is True
    assert tool_result.structured_content["data"]["vehicle_id"] == "unknown"
    assert seen["model_configs"] == {
        "lnn": {
            "auxiliary_uris": {"timespans": "file:///times.npy"},
            "lora": False,
        },
    }


def test_chronos_without_sealed_ref_fails_before_dataset(tmp_path: Path) -> None:
    result = _run(tmp_path, ["chronos"], {})
    assert result["stage"] == "preflight"
    assert "sealed local_backbone_ref" in result["error"]


def test_every_requested_family_is_preflighted_before_dataset(tmp_path: Path) -> None:
    result = _run(
        tmp_path, ["lnn", "lightgbm"],
        {"lightgbm": {"auxiliary_uris": {}}},
    )
    assert result["stage"] == "preflight"
    assert "not supported by lightgbm" in result["error"]


def test_closed_chronos_lora_contract_fails_before_ref_or_dataset(tmp_path: Path) -> None:
    result = _run(tmp_path, ["chronos"], {"chronos": {
        "local_backbone_ref": _fake_ref(tmp_path),
        "lora": True,
        "lora_config": {
            "rank": 8, "alpha": 16, "dropout": 0.05,
            "target_modules": ["wrong.target"], "quantization_bits": None,
        },
    }})
    assert result["stage"] == "preflight"
    assert "approved closed contract" in result["error"]


@pytest.mark.parametrize("extra", ["chronos", "lnn"])
def test_unrequested_family_config_fails_before_dataset(
    tmp_path: Path, extra: str,
) -> None:
    result = _run(tmp_path, ["lightgbm"], {extra: {}})
    assert result["stage"] == "preflight"
    assert "unrequested families" in result["error"]
