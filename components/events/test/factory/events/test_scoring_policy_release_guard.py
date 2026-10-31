"""S4b guard: eval/lever/chat-turn signals must never route through the
scoring policy (they own their reward paths — governance gates, not scores).
Mirrors the dedicated-handler ownership pattern in
test_generic_score_dispatch_break.py (TestDisabledPolicyNoDoubleScore).
"""
from factory.events.runtime.generic_score_dispatch import load_scoring_policy, match_policy


def test_reward_gate_event_types_absent_from_scoring_policy() -> None:
    """Payout governance types stay out of scoring_policy.yaml entirely.

    eval.* signals are the payout release gate and chat.turn.completed /
    lever.* adjustments have dedicated handlers; routing them through the
    generic scorer would double-score and break the eval-gated payout
    single-credit guarantee (available at peak budget).
    """
    policies = load_scoring_policy()
    for event_type in (
        "eval.completed", "eval.failed", "eval.started",
        "chat.turn.completed", "chat.feedback",
        "lever.adjusted", "lever.proposed",
        "blockchain.reward.escrowed",
        "blockchain.reward.released",
        "wallet.rewarded",
    ):
        matched = match_policy(event_type, policies)
        assert matched is None, f"DOUBLE-REWARD: '{event_type}' matched policy '{matched}'"


def test_no_overbroad_wildcards_in_scoring_policy() -> None:
    patterns = [p.pattern for p in load_scoring_policy()]
    for wildcard in ("*", "*.completed", "*.*"):
        assert wildcard not in patterns, f"OVERBROAD: '{wildcard}' would capture gated events"
