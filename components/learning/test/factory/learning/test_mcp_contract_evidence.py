"""Cross-brick envelope, legacy-validator, and evidence-boundary tests."""
from __future__ import annotations

import asyncio
import json
from typing import Any

import pytest
from hypothesis import given, settings, strategies as st

from factory.learning.mcp.contracts import ComputeRewardOutput
from factory.learning.runtime.adapters.mcp_result import (
    successful_data,
    validate_evals_result,
    validate_games_result,
)
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime
from factory.learning.server import create_mcp_server
from factory.mcp_utils.interface import ToolResult


def _server():
    return create_mcp_server(LearningRuntime(RewardSourceRegistry()))


def test_cross_brick_result_normalizer_accepts_typed_serialized_and_rejects_failures() -> None:
    payload = {"source_id": "games", "gt_entries_count": 2, "scoring": {"f1": 0.5}}
    typed = ToolResult(ok=True, data=payload)
    assert successful_data(typed) == payload
    assert successful_data(typed.model_dump(mode="json")) == payload
    assert successful_data(ToolResult(ok=False, error="games unavailable")) is None
    assert successful_data(
        ToolResult(ok=False, error="games unavailable").model_dump(mode="json")
    ) is None


@settings(max_examples=40, deadline=None)
@given(
    payload=st.dictionaries(
        st.text(min_size=1).filter(lambda key: key != "error"),
        st.integers(min_value=-1_000_000_000, max_value=1_000_000_000),
        max_size=8,
    )
)
def test_cross_brick_result_normalizer_property_preserves_success_data(
    payload: dict[str, int],
) -> None:
    assert successful_data(ToolResult(ok=True, data=payload)) == payload


def test_bare_mapping_requires_explicit_legacy_validator() -> None:
    payload = {"source_id": "games", "gt_entries_count": 2, "scoring": {"f1": 0.5}}
    assert successful_data(payload) is None
    assert successful_data(payload, allow_legacy=True) is None
    assert successful_data(
        payload,
        allow_legacy=True,
        validator=validate_games_result,
    ) == payload


def test_legacy_games_validator_keeps_large_counts_and_rejects_bad_scores() -> None:
    payload = {"gt_entries_count": 1025, "scoring": {"f1": 1.0}}
    assert validate_games_result(payload) == payload
    assert validate_games_result({
        "gt_entries_count": 1, "scoring": {"f1": 1.1},
    }) is None


@pytest.mark.parametrize(
    ("payload", "valid"),
    [
        ({"aggregate": {"avg_score": 0.8}}, True),
        ({"pass_rate": 0.0}, True),
        ({"summary": {"score": 1.0}}, True),
        ({"aggregate": {"avg_score": 1.1}}, False),
        ({"error": "failed", "aggregate": {"avg_score": 0.9}}, False),
    ],
)
def test_legacy_evals_validator_is_bounded_and_error_first(
    payload: dict[str, object], valid: bool,
) -> None:
    result = validate_evals_result(payload)
    assert (result == payload) is valid


@pytest.mark.parametrize(
    "payload",
    [
        {"ok": False, "aggregate": {"avg_score": 0.9}},
        {"ok": 1, "aggregate": {"avg_score": 0.9}},
        {"error": "", "aggregate": {"avg_score": 0.9}},
        {"error": False, "aggregate": {"avg_score": 0.9}},
        {"status": " timed-out ", "aggregate": {"avg_score": 0.9}},
    ],
)
def test_legacy_evals_validator_rejects_failed_envelope_markers(
    payload: dict[str, object],
) -> None:
    assert validate_evals_result(payload) is None


def test_serialized_success_with_error_is_rejected() -> None:
    payload = {
        "schema_version": "v1", "ok": True,
        "data": {"aggregate": {"avg_score": 0.9}}, "error": "unexpected",
    }
    assert successful_data(
        payload, allow_legacy=True, validator=validate_evals_result,
    ) is None


def test_games_validator_rejects_explicit_failed_envelopes() -> None:
    payload = {"ok": False, "gt_entries_count": 1, "scoring": {"f1": 0.5}}
    assert validate_games_result(payload) is None


def test_learning_output_evidence_is_bounded_and_finite() -> None:
    with pytest.raises(ValueError):
        ComputeRewardOutput(raw={"text": "x" * 65_537})
    with pytest.raises(ValueError):
        ComputeRewardOutput(raw={"score": float("nan")})
    with pytest.raises(ValueError):
        ComputeRewardOutput(raw={"integer": 1_000_000_001})
    accepted_object = {str(index): index for index in range(256)}
    accepted_list = list(range(256))
    object_output = ComputeRewardOutput(raw=accepted_object)
    list_output = ComputeRewardOutput(raw={"list": accepted_list})
    assert object_output.raw == accepted_object
    assert list_output.raw["list"] == accepted_list
    for evidence in (
        {str(index): index for index in range(257)},
        {"list": list(range(257))},
    ):
        with pytest.raises(ValueError):
            ComputeRewardOutput(raw=evidence)
    nested: dict[str, object] = {}
    cursor = nested
    for _ in range(13):
        cursor["next"] = {}
        cursor = cursor["next"]  # type: ignore[assignment]
    with pytest.raises(ValueError):
        ComputeRewardOutput(raw={"nested": nested})


def test_malformed_serialized_schema_version_is_rejected() -> None:
    payload = {"source_id": "games"}
    assert successful_data({
        "schema_version": "v2", "ok": True, "data": payload,
    }) is None
    assert successful_data({
        "schema_version": 1, "ok": True, "data": payload,
    }) is None


def test_resources_remain_native_strings_and_document_the_envelope() -> None:
    server = _server()
    schema_result = asyncio.run(server.read_resource("learning://schemas/reward-signal"))
    docs_result = asyncio.run(server.read_resource("learning://docs/learning"))
    schema = json.loads(schema_result.contents[0].content)
    docs = docs_result.contents[0].content

    assert schema["properties"]["scalar"]["minimum"] == -1
    assert schema["properties"]["scalar"]["maximum"] == 1
    assert schema["properties"]["reward_value"]["maximum"] == 1_000_000.0
    assert schema["properties"]["wallet_id"]["pattern"] == r"^[A-Za-z0-9_.:-]{1,128}$"
    assert set(schema["required"]) >= {
        "source_id", "scalar", "verdict", "reward_value", "wallet_id",
    }
    assert schema["additionalProperties"] is False
    assert "penalized" in schema["properties"]["verdict"]["enum"]
    assert "versioned ToolResult envelope" in docs
    assert "learning_compute_reward" in docs


@pytest.mark.parametrize(
    "payload",
    [
        {"summary": {"avg_score": 0.9, "error": "one evaluator failed"}},
        {"aggregate": {"score": 0.9, "error": "aggregate failed"}},
        {"summary": {"pass_rate": 0.9, "error_count": 1}},
        {"results": [{"score": 0.9, "label": "error"}], "summary": {"pass_rate": 0.9}},
    ],
)
def test_legacy_evals_validator_rejects_nested_errors(payload: dict[str, object]) -> None:
    assert validate_evals_result(payload) is None


def test_typed_learning_envelope_obeys_total_size_limit() -> None:
    payload = {**{
        "source_id": "games", "gt_entries_count": 1,
        "scoring": {"f1": 0.5},
    }, "evidence": ["x" * 60_000] * 20}
    assert successful_data(ToolResult(ok=True, data=payload)) is None
