"""ToolResult envelope regression coverage for Games RL scoring."""
from __future__ import annotations

import pytest

from factory.games.runtime._rl_stages import _score
from factory.mcp_utils.interface import ToolResult


def test_score_unwraps_tool_result_object_and_public_envelope() -> None:
    gt_entries = [{"id": "gt-1"}]
    payload = {"f1": 0.82, "precision": 0.8, "recall": 0.84}
    object_score = _score(
        lambda *_args, **_kwargs: ToolResult(data=payload), [], gt_entries,
    )
    envelope_score = _score(
        lambda *_args, **_kwargs: {
            "schema_version": "v1", "ok": True, "data": payload,
            "error": None, "idempotency_key": None,
        }, [], gt_entries,
    )
    assert object_score == payload
    assert envelope_score == payload


def test_score_rejects_bare_v2_and_invalid_success_results() -> None:
    gt_entries = [{"id": "gt-1"}]
    payload = {"f1": 0.82, "precision": 0.8, "recall": 0.84}

    for result in (
        payload,
        {"schema_version": "v2", "ok": True, "data": payload},
        ToolResult(data={"precision": 0.8}),
        ToolResult(data={"f1": 0.8, "error": "partial failure"}),
    ):
        score = _score(lambda *_args, result=result, **_kwargs: result, [], gt_entries)
        assert score == {"f1": 0, "error": "Evals score failed"}


def test_score_forwards_explicit_empty_match_on() -> None:
    captured: dict[str, object] = {}

    def invoke(_name: str, **kwargs: object) -> ToolResult:
        captured.update(kwargs)
        return ToolResult(data={"f1": 0.5})

    assert _score(invoke, [], [{"id": "gt-1"}], match_on=[]) == {"f1": 0.5}
    assert captured["match_on"] == []


@pytest.mark.parametrize(
    "evidence",
    [
        ["x"] * 1_025,
        [10**9 + 1],
        [[[[[[[[[[[[["too-deep"]]]]]]]]]]]]],
        [float("nan")],
    ],
)
def test_score_rejects_unbounded_typed_and_serialized_evidence(evidence) -> None:
    gt_entries = [{"id": "gt-1"}]
    payload = {"f1": 0.5, "matched": evidence}
    results = (
        ToolResult(data=payload),
        {
            "schema_version": "v1", "ok": True, "data": payload,
            "error": None, "idempotency_key": None,
        },
    )
    for result in results:
        score = _score(lambda *_args, result=result, **_kwargs: result, [], gt_entries)
        assert score == {"f1": 0, "error": "Evals score failed"}


def test_score_rejects_typed_evidence_over_total_utf8_limit() -> None:
    gt_entries = [{"id": "gt-1"}]
    payload = {"f1": 0.5, "matched": ["x" * 60_000] * 20}
    result = _score(lambda *_args, **_kwargs: ToolResult(data=payload), [], gt_entries)
    assert result == {"f1": 0, "error": "Evals score failed"}
