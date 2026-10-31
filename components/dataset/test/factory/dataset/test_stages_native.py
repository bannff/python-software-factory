"""Behavior tests for agentinstruct + s2m with a mock CompletionPort.

apigenmt + reviewinstruct live in test_stages_native_tools.py (LOC split).
"""

from __future__ import annotations

import json

import pytest

from factory.dataset.runtime.adapters.mock_completion import MockCompletionAdapter
from factory.dataset.runtime.records import ConversationRecord
from factory.dataset.runtime.stages import agentinstruct, s2m


def _record(*contents: str, id: str = "rec-1", metadata: dict | None = None) -> ConversationRecord:
    roles = ["user", "assistant"]
    messages = [
        {"role": roles[i % 2], "content": content} for i, content in enumerate(contents)
    ]
    return ConversationRecord(messages=messages, id=id, metadata=metadata)


# ── agentinstruct ────────────────────────────────────────────────────────────


def test_agentinstruct_fans_out_k_llm_variants_with_metadata_contract() -> None:
    completion = MockCompletionAdapter(
        responses=["variant one", "variant two", "variant three"]
    )
    out = list(
        agentinstruct(
            [_record("seed instruction", metadata={"origin": "test"})],
            k_variants=3,
            transforms=["qa", "writing", "coding"],
            completion=completion,
        )
    )

    assert len(out) == 3
    for i, rec in enumerate(out, start=1):
        meta = rec.metadata
        assert rec.id == f"rec-1::v{i}"
        assert meta["stage"] == "agentinstruct"
        assert meta["origin_id"] == "rec-1"
        assert meta["variant_id"] == f"v{i}"
        assert meta["transform_type"] in ("qa", "writing", "coding")
        assert 0.0 <= meta["diversity_score"] <= 1.0
        assert meta["llm_generated"] is True
        assert meta["model"] == "mock/deterministic"
        assert meta["origin"] == "test"  # original metadata preserved
    assert {r.messages[0].content for r in out} == {"variant one", "variant two", "variant three"}


def test_agentinstruct_dedupes_identical_variants() -> None:
    completion = MockCompletionAdapter(responses=["same text", "same text", "unique text"])
    out = list(
        agentinstruct(
            [_record("seed")],
            k_variants=3,
            transforms=["qa", "writing", "coding"],
            dedupe=True,
            completion=completion,
        )
    )
    assert len(out) == 2
    assert {r.messages[0].content for r in out} == {"same text", "unique text"}


def test_agentinstruct_deterministic_fallback_needs_no_completion() -> None:
    out = list(agentinstruct([_record("seed")], k_variants=2, use_llm=False))
    assert len(out) == 2
    assert all(r.metadata["llm_generated"] is False for r in out)
    assert all(r.metadata["model"] is None for r in out)
    assert out[0].messages[0].content.startswith("seed")


def test_agentinstruct_requires_completion_when_llm_enabled() -> None:
    with pytest.raises(ValueError, match="requires a bound completion port"):
        list(agentinstruct([_record("seed")], use_llm=True))


def test_agentinstruct_passes_through_records_without_user_message() -> None:
    rec = ConversationRecord(messages=[{"role": "system", "content": "sys"}])
    out = list(agentinstruct([rec], use_llm=False))
    assert out == [rec]


# ── s2m ──────────────────────────────────────────────────────────────────────


def test_s2m_expands_single_turn_via_llm_json() -> None:
    generated = [
        {"role": "user", "content": "q1"},
        {"role": "assistant", "content": "a1"},
        {"role": "user", "content": "q2"},
        {"role": "assistant", "content": "a2"},
    ]
    completion = MockCompletionAdapter(
        responses=["```json\n" + json.dumps(generated) + "\n```"]
    )
    out = list(s2m([_record("question", "answer")], completion=completion))

    assert len(out) == 1
    assert len(out[0].messages) == 4
    meta = out[0].metadata
    assert meta["stage"] == "s2m"
    assert meta["via"] == "llm"
    assert meta["original_turns"] == 2
    assert meta["generated_turns"] == 4
    assert meta["model"] == "mock/deterministic"


def test_s2m_passes_through_already_multiturn_records() -> None:
    rec = _record("q1", "a1", "q2", "a2")
    completion = MockCompletionAdapter()
    out = list(s2m([rec], completion=completion))
    assert out == [rec]
    assert completion.calls == []


def test_s2m_falls_back_when_llm_json_is_unparseable() -> None:
    completion = MockCompletionAdapter(responses=["not json at all"])
    out = list(s2m([_record("question", "answer")], completion=completion))
    assert out[0].metadata["via"] == "fallback"
    assert len(out[0].messages) == 4


def test_s2m_deterministic_fallback_without_llm() -> None:
    out = list(s2m([_record("question", "answer")], use_llm=False))
    assert out[0].metadata["via"] == "fallback"
    assert out[0].messages[2].content == "Can you provide an example?"


def test_s2m_truncates_to_max_turns() -> None:
    generated = [
        {"role": "user" if i % 2 == 0 else "assistant", "content": f"m{i}"} for i in range(8)
    ]
    completion = MockCompletionAdapter(responses=[json.dumps(generated)])
    out = list(s2m([_record("q", "a")], max_turns=6, completion=completion))
    assert len(out[0].messages) == 6
