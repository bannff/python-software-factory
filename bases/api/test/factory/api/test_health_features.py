from __future__ import annotations

import asyncio

from factory.api.runtime.health_features import feature_availability


def _run(caps, side_chat):
    async def call(name, args):
        return caps
    return asyncio.run(feature_availability(call, side_chat))


def test_missing_ml_group_is_named_with_the_fix() -> None:
    caps = {"ok": True, "data": {"training_available": False, "training_missing": ["torch"],
                                 "training_install_hint": "uv sync --group ml"}}
    out = _run(caps, {"status": "unavailable", "reason": "No module named 'langchain_openai'"})
    assert out["ml_training"] == {"available": False, "missing": ["torch"], "fix": "uv sync --group ml"}
    assert out["side_chat_tools"] == {"available": False, "reason": "No module named 'langchain_openai'"}


def test_available_and_unknown_states() -> None:
    assert _run({"data": {"training_available": True}}, {"status": "ready"})["ml_training"] == {"available": True}
    assert _run(None, {"status": "ready"})["ml_training"] == {"available": None}
