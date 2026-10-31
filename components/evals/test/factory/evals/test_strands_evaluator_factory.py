"""One polymorphic evaluator factory, framework selected by parameter."""
from __future__ import annotations

import pytest

from factory.evals.runtime.adapters import evaluator_factory as ef


def test_single_registry_binds_both_frameworks():
    """Every alias carries both a local label and a pinned SDK class name."""
    for alias, spec in ef.EVALUATOR_REGISTRY.items():
        assert spec.class_name, alias
        assert spec.sdk_class_name, alias
    assert set(ef.EVALUATOR_FRAMEWORKS) == {"strands"}


def test_build_evaluators_returns_raw_sdk_judges_by_default():
    """build_evaluators is now the SDK Experiment helper; default = strands."""
    built = ef.build_evaluators(["output", "helpfulness"])
    assert type(built[0]).__name__ == "OutputEvaluator"
    assert type(built[1]).__name__ == "HelpfulnessEvaluator"


def test_strands_framework_returns_pinned_sdk_evaluators():
    built = ef.build_evaluators(["output"], rubric="be terse", framework="strands")
    assert len(built) == 1
    assert type(built[0]).__name__ == "OutputEvaluator"


def test_alias_round_trip_across_frameworks():
    for alias in ef.EVALUATOR_REGISTRY:
        built, = ef.build_evaluators([alias], rubric="r", framework="strands")
        assert ef.alias_for_evaluator(built, framework="strands") == alias


def test_unknown_framework_and_alias_are_fail_closed():
    with pytest.raises(ValueError, match="unknown evaluator framework"):
        ef.build_evaluators(["output"], framework="nope")
    with pytest.raises(ValueError, match="unknown evaluator"):
        ef.build_evaluators(["does-not-exist"], framework="strands")
