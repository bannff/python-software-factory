"""SDK judges must receive a resolved model, not a raw ollama: id (issue #321)."""
import pytest

from factory.evals.runtime.adapters.evaluator_factory import build_evaluators
from factory.evals.runtime.adapters.experiment_runner import count_evaluation_errors


def test_ollama_judge_gets_model_object_not_bedrock_string(monkeypatch):
    monkeypatch.setenv("COMPANION_X_EVAL_MODEL", "ollama:gemma4:12b")
    monkeypatch.delenv("COMPANION_X_EVAL_JUDGE_MODEL", raising=False)
    judge = build_evaluators(["helpfulness"])[0]
    assert not isinstance(judge.model, str)


def test_bare_bedrock_id_stays_a_string(monkeypatch):
    monkeypatch.delenv("COMPANION_X_EVAL_MODEL", raising=False)
    monkeypatch.setenv("COMPANION_X_EVAL_JUDGE_MODEL", "some.bedrock.id")
    judge = build_evaluators(["helpfulness"])[0]
    assert judge.model == "some.bedrock.id"


@pytest.mark.parametrize("rows,expected", [
    ([], 0),
    ([{"reason": "ok"}, {"reason": "Evaluator error: boom"}], 1),
    ([{"reason": "Evaluator error: a"}, {"reason": "Evaluator error: b"}], 2),
])
def test_count_evaluation_errors(rows, expected):
    assert count_evaluation_errors(rows) == expected
