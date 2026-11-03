from __future__ import annotations

import sys
import types

import pytest

from factory.evals.runtime.adapters import model_resolver as mr
from factory.evals.runtime.adapters._judge_model import judge_model_id


def test_bare_ids_stay_bedrock_and_ollama_ids_become_model_objects(monkeypatch) -> None:
    seen = {}

    class FakeOpenAIModel:
        def __init__(self, client_args, model_id):
            seen.update(client_args=client_args, model_id=model_id)

    fake_pkg = types.ModuleType("strands.models.openai")
    fake_pkg.OpenAIModel = FakeOpenAIModel
    monkeypatch.setitem(sys.modules, "strands.models.openai", fake_pkg)
    monkeypatch.delenv("OLLAMA_BASE_URL", raising=False)
    assert mr.resolve_agent_model("us.anthropic.claude-x") == "us.anthropic.claude-x"
    mr.resolve_agent_model("ollama:gemma4:12b")
    assert seen["model_id"] == "gemma4:12b"
    assert seen["client_args"]["base_url"] == "http://localhost:11434/v1"


def test_judge_routes_by_prefix(monkeypatch) -> None:
    calls = []
    fake = types.ModuleType("langchain.chat_models")
    fake.init_chat_model = lambda spec, **kw: calls.append((spec, kw)) or object()
    monkeypatch.setitem(sys.modules, "langchain.chat_models", fake)
    mr.resolve_judge_model("ollama:gemma4:12b")
    mr.resolve_judge_model("us.anthropic.claude-x")
    assert calls[0][0] == "openai:gemma4:12b" and calls[0][1]["api_key"] == "ollama"
    assert calls[1] == ("bedrock_converse:us.anthropic.claude-x", {})


def test_one_env_var_sets_agent_and_judge_defaults(monkeypatch) -> None:
    monkeypatch.delenv("COMPANION_X_EVAL_JUDGE_MODEL", raising=False)
    monkeypatch.setenv("COMPANION_X_EVAL_MODEL", "ollama:gemma4:12b")
    assert mr.default_model_id() == judge_model_id() == "ollama:gemma4:12b"
    monkeypatch.setenv("COMPANION_X_EVAL_JUDGE_MODEL", "ollama:other")
    assert judge_model_id() == "ollama:other"


@pytest.mark.parametrize(("error", "expected"), [
    (RuntimeError("Unable to locate credentials"), True),
    (ConnectionError("Connection refused"), True),
    (KeyError("case"), False),
])
def test_model_unavailable_classification(error, expected) -> None:
    assert mr.is_model_unavailable(error) is expected
