"""Signed-scalar, user-feedback, and telemetry reward-source tests."""

from factory.learning.runtime.adapters.gt_findings import GtFindingsRewardSource
from factory.learning.runtime.adapters.llm_judge import LlmJudgeRewardSource
from factory.learning.runtime.adapters.telemetry import TelemetryRewardSource
from factory.learning.runtime.adapters.user_feedback import UserFeedbackRewardSource
from factory.learning.runtime.models import RewardSignal
from factory.learning.runtime.registry import RewardSourceRegistry
from factory.learning.runtime.runtime import LearningRuntime


# -- signed scalar (negative learning signal, never mints) ------------------

def test_from_scalar_positive_is_byte_identical() -> None:
    sig = RewardSignal.from_scalar("x", 0.5)
    assert sig.scalar == 0.5
    assert sig.reward_value == 50.0
    assert sig.verdict == "rewarded"


def test_from_scalar_zero_is_no_reward() -> None:
    sig = RewardSignal.from_scalar("x", 0.0)
    assert sig.reward_value == 0.0
    assert sig.verdict == "no_reward"


def test_from_scalar_negative_floors_tokens_and_penalizes() -> None:
    sig = RewardSignal.from_scalar("x", -1.0)
    assert sig.scalar == -1.0          # signed signal preserved for learning
    assert sig.reward_value == 0.0      # NEVER mints negative
    assert sig.verdict == "penalized"


def test_from_scalar_clamps_to_signed_unit_range() -> None:
    assert RewardSignal.from_scalar("x", 5.0).scalar == 1.0
    assert RewardSignal.from_scalar("x", -5.0).scalar == -1.0


# -- user-feedback source (explicit human signal) ---------------------------

def test_user_feedback_up_rewards() -> None:
    sig = UserFeedbackRewardSource().signal_or_none(
        {"feedback_verdict": "up", "thread_id": "t1"}, None)
    assert sig is not None
    assert sig.source_id == "user-feedback"
    assert sig.scalar == 1.0
    assert sig.reward_value == 100.0
    assert sig.verdict == "rewarded"
    assert sig.provenance["feedback_verdict"] == "up"


def test_user_feedback_down_penalizes_without_minting() -> None:
    sig = UserFeedbackRewardSource().signal_or_none({"feedback_verdict": "down"}, None)
    assert sig is not None
    assert sig.scalar == -1.0
    assert sig.reward_value == 0.0
    assert sig.verdict == "penalized"


def test_user_feedback_abstains_without_verdict() -> None:
    assert UserFeedbackRewardSource().signal_or_none({"run_id": "r"}, None) is None


def test_runtime_routes_explicit_feedback_to_user_feedback_source() -> None:
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(LlmJudgeRewardSource())
    reg.register_builtin(UserFeedbackRewardSource())
    rt = LearningRuntime(reg)
    # No graph_id (gt abstains), no output (llm-judge abstains) → feedback wins.
    out = rt.compute({"run_id": "chat-1", "feedback_verdict": "up"}, lambda *a, **k: {})
    assert out["source_id"] == "user-feedback"
    assert out["reward_value"] == 100.0
    assert out["verdict"] == "rewarded"


# -- telemetry source (process-health → negative learning signal) -----------

def test_telemetry_penalizes_proportional_to_error_rate() -> None:
    sig = TelemetryRewardSource().signal_or_none({"tool_error_rate": 0.4}, None)
    assert sig is not None
    assert sig.source_id == "telemetry"
    assert sig.scalar == -0.4
    assert sig.reward_value == 0.0        # negative never mints
    assert sig.verdict == "penalized"
    assert sig.provenance["tool_error_rate"] == 0.4


def test_telemetry_abstains_on_clean_run() -> None:
    assert TelemetryRewardSource().signal_or_none({"tool_error_rate": 0.0}, None) is None
    assert TelemetryRewardSource().signal_or_none({"run_id": "r"}, None) is None  # missing


def test_telemetry_clamps_error_rate() -> None:
    sig = TelemetryRewardSource().signal_or_none({"tool_error_rate": 1.5}, None)
    assert sig is not None
    assert sig.scalar == -1.0


def test_runtime_routes_telemetry_when_only_error_rate_present() -> None:
    reg = RewardSourceRegistry()
    reg.register_builtin(GtFindingsRewardSource())
    reg.register_builtin(LlmJudgeRewardSource())
    reg.register_builtin(UserFeedbackRewardSource())
    reg.register_builtin(TelemetryRewardSource())
    rt = LearningRuntime(reg)
    # No graph_id / output / feedback → only telemetry fires.
    out = rt.compute({"run_id": "r1", "tool_error_rate": 0.5}, lambda *a, **k: {})
    assert out["source_id"] == "telemetry"
    assert out["verdict"] == "penalized"
    assert out["reward_value"] == 0.0
