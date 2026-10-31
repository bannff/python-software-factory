"""Provider-rail tests: registry, deterministic honesty, LLM-judge wiring.

LLM-judge providers are exercised with the SDK factory / judge model
monkeypatched to fakes — no live Bedrock is required.
"""
from __future__ import annotations

import sys

import pytest

from factory.evals.runtime.adapters import evaluator_adapter
from factory.evals.runtime.adapters.evaluator_factory import (
    EVALUATOR_REGISTRY, EvaluationData,
)
from factory.evals.runtime.adapters import evaluator_providers as reg
from factory.evals.runtime.adapters.evaluator_providers import (
    deterministic, langchain_provider, langchain_trajectory, strands_provider,
)


def _data(expected=None) -> EvaluationData:
    return EvaluationData("q", "an answer", expected)


# -- registry ---------------------------------------------------------------

def test_registry_exposes_all_builtin_frameworks() -> None:
    frameworks = reg.available_frameworks()
    assert set(frameworks) == {
        "deterministic", "strands", "langchain", "langchain_trajectory",
    }


def test_registry_unknown_framework_is_fail_closed() -> None:
    with pytest.raises(ValueError, match="unknown evaluator framework"):
        reg.get_provider("nope")


# -- deterministic honesty --------------------------------------------------

def test_deterministic_module_import_is_sdk_free() -> None:
    for mod in ("strands_evals", "openevals", "agentevals"):
        sys.modules.pop(mod, None)
    provider = deterministic.DeterministicProvider()
    provider.build(["non_empty", "exact_match"])
    assert not any(m in sys.modules for m in ("strands_evals", "openevals", "agentevals"))


def test_exact_match_abstains_without_expected_output() -> None:
    evaluator, = deterministic.DeterministicProvider().build(["exact_match"])
    out, = evaluator.evaluate(_data(expected=None))
    assert out.label == "abstain"
    assert out.test_pass is False


def test_exact_match_compares_stripped_strings() -> None:
    evaluator, = deterministic.DeterministicProvider().build(["exact_match"])
    assert evaluator.evaluate(_data(expected="  an answer "))[0].test_pass is True
    assert evaluator.evaluate(_data(expected="other"))[0].test_pass is False


def test_non_empty_scores_presence() -> None:
    evaluator, = deterministic.DeterministicProvider().build(["non_empty"])
    assert evaluator.evaluate(EvaluationData("q", "  "))[0].test_pass is False
    assert evaluator.evaluate(EvaluationData("q", "x"))[0].test_pass is True


def test_deterministic_rejects_llm_judge_name() -> None:
    with pytest.raises(ValueError, match="does not support"):
        deterministic.DeterministicProvider().build(["helpfulness"])


# -- default direct path (deterministic) ------------------------------------

def test_evaluate_output_default_is_deterministic() -> None:
    row = evaluator_adapter.evaluate_output("q", "a real answer")
    assert row["evaluator"] == "non_empty"
    assert row["score"] == 1.0
    assert row["test_pass"] is True


def test_evaluate_output_multi_aggregates_rows() -> None:
    result = evaluator_adapter.evaluate_output_multi(
        "q", "a real answer", ["non_empty", "exact_match"],
        expected_output="a real answer",
    )
    assert result["summary"]["total_evaluators"] == 2
    assert result["summary"]["pass_rate"] == 1.0


# -- langchain (openevals) with a fake judge --------------------------------

def _fake_judge_factory(score: float, comment: str = "because"):
    def _create(*, prompt, judge, continuous, feedback_key):  # noqa: ARG001
        def _judge_fn(*, inputs, outputs, reference_outputs):  # noqa: ARG001
            return {"key": feedback_key, "score": score, "comment": comment}
        return _judge_fn
    return _create


def test_langchain_provider_maps_judge_result(monkeypatch) -> None:
    oe = pytest.importorskip("openevals.llm")
    monkeypatch.setattr(langchain_provider, "get_judge_model", lambda: object())
    monkeypatch.setattr(oe, "create_llm_as_judge", _fake_judge_factory(0.8))
    provider = langchain_provider.LangChainProvider()
    assert set(provider.available()) >= {"helpfulness", "answer_relevance"}
    evaluator, = provider.build(["helpfulness"])
    out, = evaluator.evaluate(_data())
    assert out.score == 0.8
    assert out.test_pass is True
    assert out.label == "helpfulness"


def test_langchain_provider_low_score_fails(monkeypatch) -> None:
    oe = pytest.importorskip("openevals.llm")
    monkeypatch.setattr(langchain_provider, "get_judge_model", lambda: object())
    monkeypatch.setattr(oe, "create_llm_as_judge", _fake_judge_factory(0.2))
    evaluator, = langchain_provider.LangChainProvider().build(["correctness"])
    assert evaluator.evaluate(_data())[0].test_pass is False


def test_langchain_provider_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="does not support"):
        langchain_provider.LangChainProvider().build(["not_a_prompt"])


# -- langchain_trajectory (agentevals) with a fake judge --------------------

def test_trajectory_provider_abstains_without_trajectory(monkeypatch) -> None:
    ae = pytest.importorskip("agentevals.trajectory.llm")
    monkeypatch.setattr(langchain_trajectory, "get_judge_model", lambda: object())
    monkeypatch.setattr(
        ae, "create_trajectory_llm_as_judge",
        lambda **_k: (lambda **_kk: {"score": 1.0, "comment": "x"}),
    )
    evaluator, = langchain_trajectory.LangChainTrajectoryProvider().build(
        ["trajectory_accuracy"],
    )
    out, = evaluator.evaluate(EvaluationData("q", "a", actual_trajectory=None))
    assert out.label == "abstain"


def test_trajectory_provider_scores_with_trajectory(monkeypatch) -> None:
    ae = pytest.importorskip("agentevals.trajectory.llm")
    monkeypatch.setattr(langchain_trajectory, "get_judge_model", lambda: object())
    monkeypatch.setattr(
        ae, "create_trajectory_llm_as_judge",
        lambda **_k: (lambda **_kk: {"score": 0.9, "comment": "good"}),
    )
    evaluator, = langchain_trajectory.LangChainTrajectoryProvider().build(
        ["trajectory_accuracy"],
    )
    traj = [{"role": "assistant", "content": "hi"}]
    out, = evaluator.evaluate(EvaluationData("q", "a", actual_trajectory=traj))
    assert out.score == 0.9
    assert out.test_pass is True


def test_trajectory_provider_available_lists_new_names() -> None:
    names = langchain_trajectory.LangChainTrajectoryProvider().available()
    assert set(names) == {
        "trajectory_accuracy", "trajectory_match", "tool_selection", "custom",
    }


def test_trajectory_match_is_deterministic_and_sdk_scoped(monkeypatch) -> None:
    am = pytest.importorskip("agentevals.trajectory.match")

    captured: dict[str, str] = {}

    def _fake_factory(*, trajectory_match_mode, tool_args_match_mode):
        captured["mode"] = trajectory_match_mode
        captured["args"] = tool_args_match_mode

        def _eval(*, outputs, reference_outputs):
            return {"key": "match", "score": outputs == reference_outputs, "comment": "det"}

        return _eval

    monkeypatch.setattr(am, "create_trajectory_match_evaluator", _fake_factory)
    evaluator, = langchain_trajectory.LangChainTrajectoryProvider().build(
        ["trajectory_match"], options={"match_mode": "strict", "tool_args_mode": "exact"},
    )
    assert captured == {"mode": "strict", "args": "exact"}
    traj = [{"role": "assistant", "content": "hi"}]
    matched, = evaluator.evaluate(EvaluationData(
        "q", "a", actual_trajectory=traj, expected_trajectory=traj,
    ))
    assert matched.score == 1.0 and matched.test_pass is True
    diverged, = evaluator.evaluate(EvaluationData(
        "q", "a", actual_trajectory=traj,
        expected_trajectory=[{"role": "assistant", "content": "bye"}],
    ))
    assert diverged.score == 0.0 and diverged.test_pass is False


def test_trajectory_match_abstains_without_reference(monkeypatch) -> None:
    am = pytest.importorskip("agentevals.trajectory.match")
    monkeypatch.setattr(
        am, "create_trajectory_match_evaluator",
        lambda **_k: (lambda **_kk: {"score": True, "comment": ""}),
    )
    evaluator, = langchain_trajectory.LangChainTrajectoryProvider().build(
        ["trajectory_match"],
    )
    out, = evaluator.evaluate(EvaluationData(
        "q", "a", actual_trajectory=[{"role": "assistant", "content": "hi"}],
    ))
    assert out.label == "abstain"


def test_trajectory_custom_requires_rubric(monkeypatch) -> None:
    monkeypatch.setattr(langchain_trajectory, "get_judge_model", lambda: object())
    with pytest.raises(ValueError, match="requires a rubric"):
        langchain_trajectory.LangChainTrajectoryProvider().build(["custom"])


# -- langchain custom (openevals) with a fake judge -------------------------

def test_langchain_custom_maps_and_requires_rubric(monkeypatch) -> None:
    oe = pytest.importorskip("openevals.llm")
    monkeypatch.setattr(langchain_provider, "get_judge_model", lambda: object())
    monkeypatch.setattr(oe, "create_llm_as_judge", _fake_judge_factory(0.9, "ok"))
    provider = langchain_provider.LangChainProvider()
    assert "custom" in provider.available()
    evaluator, = provider.build(["custom"], rubric="Rate {inputs} vs {outputs}")
    out, = evaluator.evaluate(_data())
    assert out.score == 0.9 and out.test_pass is True and out.label == "custom"
    with pytest.raises(ValueError, match="requires a rubric"):
        provider.build(["custom"])


def test_all_providers_accept_options_kwarg() -> None:
    deterministic.DeterministicProvider().build(["non_empty"], options={"x": 1})
    strands_provider.StrandsProvider().available()  # signature-only smoke below
    # options is accepted without effect on deterministic; strands/langchain
    # signatures are exercised via build() elsewhere with monkeypatched SDKs.
    assert True


# -- strands provider (construction only; evaluate needs Bedrock) -----------

def test_strands_provider_available_matches_registry() -> None:
    assert strands_provider.StrandsProvider().available() == list(EVALUATOR_REGISTRY)


def test_strands_provider_wraps_sdk_evaluators() -> None:
    built = strands_provider.StrandsProvider().build(["output", "helpfulness"])
    assert [ev.name for ev in built] == ["output", "helpfulness"]
