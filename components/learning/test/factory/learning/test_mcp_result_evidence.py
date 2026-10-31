"""Learning-local sequence bounds for cross-brick MCP evidence."""
from __future__ import annotations

from typing import Any, Callable

import pytest

from factory.learning.runtime.adapters.mcp_result import (
    successful_data,
    validate_evals_result,
    validate_games_result,
)
from factory.mcp_utils.interface import ToolResult


def _games_payload(items: list[int]) -> dict[str, Any]:
    return {
        "gt_entries_count": 1,
        "scoring": {"f1": 0.5},
        "evidence": items,
    }


def _evals_payload(items: list[int]) -> dict[str, Any]:
    return {"aggregate": {"avg_score": 0.5}, "evidence": items}


@pytest.mark.parametrize(
    ("builder", "validator"),
    [
        (_games_payload, validate_games_result),
        (_evals_payload, validate_evals_result),
    ],
)
@pytest.mark.parametrize(("size", "valid"), [(256, True), (257, False)])
def test_learning_validators_enforce_256_item_evidence(
    builder: Callable[[list[int]], dict[str, Any]],
    validator: Callable[[dict[str, Any]], dict[str, Any] | None],
    size: int,
    valid: bool,
) -> None:
    payload = builder(list(range(size)))
    assert (validator(payload) == payload) is valid
    assert (
        successful_data(
            payload, allow_legacy=True, validator=validator,
        ) == payload
    ) is valid


@pytest.mark.parametrize("builder", [_games_payload, _evals_payload])
@pytest.mark.parametrize(("size", "valid"), [(256, True), (257, False)])
def test_typed_and_serialized_envelopes_use_learning_limit(
    builder: Callable[[list[int]], dict[str, Any]],
    size: int,
    valid: bool,
) -> None:
    payload = builder(list(range(size)))
    expected = payload if valid else None
    results = (
        ToolResult(ok=True, data=payload),
        ToolResult(ok=True, data=payload).model_dump(mode="json"),
    )
    for result in results:
        assert successful_data(result) == expected


@pytest.mark.parametrize(
    "blockchain",
    [
        {"status": "failed", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"status": "cancelled", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"status": "timeout", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"status": "timed_out", "amount": 99.0, "wallet_id": "wallet-valid"},
        {"error": "mint_failed", "amount": 99.0, "wallet_id": "wallet-valid"},
    ],
)
def test_games_validator_rejects_failed_nested_blockchain_evidence(
    blockchain: dict[str, object],
) -> None:
    payload = {
        "gt_entries_count": 1,
        "scoring": {"f1": 0.5},
        "blockchain": blockchain,
    }
    assert validate_games_result(payload) is None
