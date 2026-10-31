"""Behavior tests for apigenmt + reviewinstruct with a mock CompletionPort.

Split from test_stages_native.py (agentinstruct + s2m) to respect the
factory's 200-LOC-per-file tenet.
"""

from __future__ import annotations

import json

import pytest

from factory.dataset.runtime.adapters.mock_completion import MockCompletionAdapter
from factory.dataset.runtime.records import ConversationRecord
from factory.dataset.runtime.stages import apigenmt, reviewinstruct


def _record(*contents: str, id: str = "rec-1", metadata: dict | None = None) -> ConversationRecord:
    roles = ["user", "assistant"]
    messages = [
        {"role": roles[i % 2], "content": content} for i, content in enumerate(contents)
    ]
    return ConversationRecord(messages=messages, id=id, metadata=metadata)


# ── apigenmt ─────────────────────────────────────────────────────────────────

_TOOLS = [
    {"name": "port_scan", "description": "Scan ports", "parameters": {"host": {"type": "string", "required": True}}},
]


def test_apigenmt_injects_tools_scoped_to_catalog() -> None:
    analysis = {
        "tool_calls": [
            {
                "after_message_index": 1,
                "tool_name": "port_scan",
                "reasoning": "user asked about open ports",
                "arguments": {"host": "example.com"},
            }
        ]
    }
    completion = MockCompletionAdapter(responses=[json.dumps(analysis), "scan result: 22/tcp open"])
    out = list(apigenmt([_record("scan example.com", "sure")], tools=_TOOLS, completion=completion))

    rec = out[0]
    assert rec.metadata["agentic"] is True
    assert rec.metadata["via"] == "llm"
    assert rec.metadata["tools_injected"] == 1
    assistant = rec.messages[1]
    assert assistant.tool_calls and assistant.tool_calls[0].name == "port_scan"
    assert assistant.tool_calls[0].arguments == {"host": "example.com"}
    tool_msg = rec.messages[2]
    assert tool_msg.role == "tool"
    assert tool_msg.tool_name == "port_scan"
    assert tool_msg.content == "scan result: 22/tcp open"
    assert tool_msg.tool_call_id == assistant.tool_calls[0].id


def test_apigenmt_no_tools_configured_passes_through() -> None:
    out = list(apigenmt([_record("hi", "hello")], tools=None))
    assert out[0].metadata == {"stage": "apigenmt", "agentic": False}


def test_apigenmt_llm_reports_no_relevant_tools() -> None:
    completion = MockCompletionAdapter(responses=[json.dumps({"tool_calls": []})])
    out = list(apigenmt([_record("hi", "hello")], tools=_TOOLS, completion=completion))
    assert out[0].metadata["via"] == "llm_no_tools"
    assert out[0].metadata["agentic"] is False


def test_apigenmt_skips_injection_on_non_assistant_index() -> None:
    analysis = {"tool_calls": [{"after_message_index": 0, "tool_name": "port_scan", "arguments": {}}]}
    completion = MockCompletionAdapter(responses=[json.dumps(analysis)])
    out = list(apigenmt([_record("hi", "hello")], tools=_TOOLS, completion=completion))
    assert out[0].metadata["tools_injected"] == 0


def test_apigenmt_use_llm_false_passes_through_disabled() -> None:
    out = list(apigenmt([_record("hi", "hello")], tools=_TOOLS, use_llm=False))
    assert out[0].metadata["via"] == "disabled"


# ── reviewinstruct ───────────────────────────────────────────────────────────


def test_reviewinstruct_accepts_above_threshold_without_refining() -> None:
    review = {"decision": "accept", "overall_score": 4.5, "issues": []}
    completion = MockCompletionAdapter(responses=[json.dumps(review)])
    out = list(reviewinstruct([_record("q", "a")], accept_threshold=3.5, completion=completion))

    assert len(out) == 1
    meta = out[0].metadata
    assert meta["stage"] == "reviewinstruct"
    assert meta["reviewed"] is True
    assert meta["via"] == "llm"
    assert meta["decision"] == "accept"
    assert meta["score"] == 4.5
    assert meta["iterations"] == 0
    # Accepted without refinement: exactly ONE completion call (the review).
    assert len(completion.calls) == 1
    assert out[0].messages[0].content == "q"


def test_reviewinstruct_refines_below_threshold_then_accepts() -> None:
    reject = {
        "decision": "refine", "overall_score": 2.0,
        "issues": ["too terse"], "refinement_guidance": "expand the answer",
    }
    refined = [
        {"role": "user", "content": "q"},
        {"role": "assistant", "content": "a much better answer"},
    ]
    accept = {"decision": "accept", "overall_score": 4.0, "issues": []}
    completion = MockCompletionAdapter(
        responses=[json.dumps(reject), json.dumps(refined), json.dumps(accept)]
    )
    out = list(
        reviewinstruct(
            [_record("q", "a")],
            accept_threshold=3.5, max_iterations=2, completion=completion,
        )
    )

    assert len(out) == 1
    meta = out[0].metadata
    assert meta["decision"] == "accept"
    assert meta["score"] == 4.0
    assert meta["iterations"] == 1
    # Refined messages replace the originals.
    assert out[0].messages[1].content == "a much better answer"
    # review → refine → re-review = three completion calls.
    assert len(completion.calls) == 3


def test_reviewinstruct_accepts_as_is_when_refinement_fails() -> None:
    reject = {"decision": "refine", "overall_score": 1.0, "issues": ["bad"]}
    completion = MockCompletionAdapter(
        responses=[json.dumps(reject), "not json at all"]
    )
    out = list(reviewinstruct([_record("q", "a")], completion=completion))

    assert len(out) == 1
    # Original messages retained; loop broke on failed refinement.
    assert out[0].messages[1].content == "a"
    assert out[0].metadata["iterations"] == 0
    assert out[0].metadata["reviewed"] is True


def test_reviewinstruct_use_llm_false_passes_through_disabled() -> None:
    out = list(reviewinstruct([_record("q", "a")], use_llm=False))
    assert out[0].metadata["via"] == "disabled"
    assert out[0].metadata["reviewed"] is False


def test_reviewinstruct_requires_completion_when_llm_enabled() -> None:
    with pytest.raises(ValueError, match="requires a bound completion port"):
        list(reviewinstruct([_record("q", "a")], use_llm=True))
