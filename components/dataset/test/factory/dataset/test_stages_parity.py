"""Parity between native generation stages and the upstream reference.

Golden fixture (``fixtures/generation_stages_parity.json``) was captured by
running the still-installed ``agentic_datasets`` v2 stages in deterministic
(``use_llm=False``) mode over fixed seed records. This test degrades to a
pure snapshot comparison once the upstream package is removed from the
venv — the fixture is the parity oracle from that point on.

Only the deterministic fallback paths are compared: LLM-backed paths are
non-reproducible across providers and are covered by ``test_stages_native``
against ``MockCompletionAdapter`` instead.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from factory.dataset.runtime.records import ConversationRecord
from factory.dataset.runtime.stages import agentinstruct, apigenmt, reviewinstruct, s2m

_FIXTURE = Path(__file__).parent / "fixtures" / "generation_stages_parity.json"

SINGLE_TURN = {
    "id": "seed-single",
    "source": "parity-fixture",
    "metadata": {"origin": "parity"},
    "messages": [
        {"role": "user", "content": "How do I rotate AWS credentials safely?"},
        {"role": "assistant", "content": "Use IAM roles and short-lived tokens."},
    ],
}
MULTI_TURN = {
    "id": "seed-multi",
    "source": "parity-fixture",
    "metadata": None,
    "messages": [
        {"role": "user", "content": "What is a CAN bus?"},
        {"role": "assistant", "content": "A vehicle message bus."},
        {"role": "user", "content": "Is it encrypted?"},
        {"role": "assistant", "content": "Classically, no."},
    ],
}
TOOLS = [
    {"name": "port_scan", "description": "Scan ports", "parameters": {}},
    {"name": "http_probe", "description": "Probe HTTP", "parameters": {}},
]


def _rec(d: dict) -> ConversationRecord:
    return ConversationRecord.model_validate(d)


def _norm(r: ConversationRecord) -> dict:
    return {
        "id": r.id,
        "source": r.source,
        "messages": [{"role": m.role, "content": m.content} for m in r.messages],
        "metadata": r.metadata,
    }


@pytest.fixture(scope="module")
def golden() -> dict:
    return json.loads(_FIXTURE.read_text())


def test_agentinstruct_deterministic_fallback_matches_upstream(golden: dict) -> None:
    out = [
        _norm(r)
        for r in agentinstruct(
            [_rec(SINGLE_TURN)], k_variants=3, transforms=["qa", "writing", "coding"],
            dedupe=True, use_llm=False,
        )
    ]
    assert out == golden["agentinstruct"]


def test_s2m_deterministic_fallback_matches_upstream(golden: dict) -> None:
    out = [_norm(r) for r in s2m([_rec(SINGLE_TURN), _rec(MULTI_TURN)], use_llm=False)]
    assert out == golden["s2m"]


def test_apigenmt_deterministic_fallback_matches_upstream(golden: dict) -> None:
    out = [_norm(r) for r in apigenmt([_rec(SINGLE_TURN)], tools=TOOLS, use_llm=False)]
    assert out == golden["apigenmt"]


def test_reviewinstruct_deterministic_fallback_matches_upstream(golden: dict) -> None:
    out = [_norm(r) for r in reviewinstruct([_rec(SINGLE_TURN)], use_llm=False)]
    assert out == golden["reviewinstruct"]


def test_upstream_still_importable_note() -> None:
    """Sentinel: once this starts failing, the fixture is the only oracle left.

    Not a hard dependency — pytest.importorskip is intentionally NOT used
    here so CI notices the moment the venv package is removed and this
    test suite quietly becomes fixture-only (expected, not a regression).
    """
    pytest.importorskip("agentic_datasets", reason="upstream removed — fixture-only parity now")
