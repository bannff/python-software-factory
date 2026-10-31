"""Phase 4: domain_class rename + back-compat + dual-tag emission.

bd:python-factory-qer1z. Cites design verdicts:
  - meta-architect 9a4aba3c-d076-48a9-9499-5e24b0931a35
  - strands-expert  9b6d46cd-ed23-4a32-b3a0-40479b845768

Verifies (a) ``config["domain_class"]`` wins over ``config["vuln_class"]``
when both are present, (b) ``config["vuln_class"]`` fallback still works
(security back-compat), (c) dual-tag emission shape, (d) Hypothesis property:
tag set always carries the domain prefix and back-compat ``scan-learnings``.

Sibling file ``test_count_labels_substrate.py`` covers the count_labels knob.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from hypothesis import given, settings, strategies as st

from factory.games.runtime.game_pipeline import process_game_finished


def _learning_payload(**config_overrides) -> dict:
    """Game.finished payload with config dict for _store_learnings."""
    return {
        "game_id": "g-001",
        "game_type": "scan",
        "winner": 1,
        "reward": {1: 1.0},
        "move_count": 1,
        "move_history": [
            {"action": "submit_finding",
             "move": {"match": "vulnerability"}},
        ],
        "config": config_overrides,
        "players": {1: "agent-alpha"},
    }


def _last_memory_call(invoker: MagicMock) -> dict:
    """Return kwargs of the most recent memory_memory_store invocation."""
    for call in reversed(invoker.call_args_list):
        if call[0] and call[0][0] == "memory_memory_store":
            return call[1]
    raise AssertionError("memory_memory_store was not invoked")


def _last_tags(invoker: MagicMock) -> list:
    """Return the tag list from the most recent memory_memory_store call.

    bd:python-factory-vs1vu — tags ride inside ``metadata={"tags": ...}``,
    not as a top-level kwarg, so they land in ``MemoryQuery.metadata.tags``
    (the shape ``memory_retrieve(tags=...)`` reads from).
    """
    kwargs = _last_memory_call(invoker)
    metadata = kwargs.get("metadata") or {}
    return metadata.get("tags", [])


class TestDomainClassRename:
    """``domain_class`` config wins over ``vuln_class``; fallback still works."""

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_domain_class_wins_when_both_present(self, mock_get):
        invoker = MagicMock(return_value={"ok": True})
        mock_get.return_value = invoker
        process_game_finished(_learning_payload(
            domain_class="wine_pairing",
            vuln_class="security_idor",  # legacy alias must lose
            run_id="r-1",
        ))
        tags = _last_tags(invoker)
        assert "wine_pairing" in tags
        assert "security_idor" not in tags
        assert "wine_pairing-learnings" in tags
        assert "scan-learnings" in tags

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_vuln_class_fallback_when_only_legacy_set(self, mock_get):
        invoker = MagicMock(return_value={"ok": True})
        mock_get.return_value = invoker
        process_game_finished(_learning_payload(
            vuln_class="security_idor",
            run_id="r-2",
        ))
        assert _last_tags(invoker) == [
            "security_idor", "scan-learnings",
            "security_idor-learnings", "r-2",
        ]

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_dual_tag_shape_for_security_idor(self, mock_get):
        invoker = MagicMock(return_value={"ok": True})
        mock_get.return_value = invoker
        process_game_finished(_learning_payload(
            domain_class="security_idor",
            run_id="r-3",
        ))
        assert _last_tags(invoker) == [
            "security_idor", "scan-learnings",
            "security_idor-learnings", "r-3",
        ]

    @patch("factory.games.runtime.game_pipeline._get_invoker")
    def test_falls_back_to_game_type_when_neither_present(self, mock_get):
        invoker = MagicMock(return_value={"ok": True})
        mock_get.return_value = invoker
        process_game_finished(_learning_payload(run_id="r-4"))
        tags = _last_tags(invoker)
        assert "scan" in tags
        assert "scan-learnings" in tags


class TestStoreLearningsTagProperties:
    """Tag list always contains domain prefix + scan-learnings + suffix."""

    @given(
        domain_class=st.text(
            min_size=1, max_size=24,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters="_-",
            ),
        ),
        run_id=st.text(
            min_size=1, max_size=24,
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters="_-",
            ),
        ),
    )
    @settings(max_examples=40, deadline=None)
    def test_tags_always_carry_domain_prefix_and_back_compat(
        self, domain_class: str, run_id: str,
    ) -> None:
        invoker = MagicMock(return_value={"ok": True})
        with patch(
            "factory.games.runtime.game_pipeline._get_invoker",
            return_value=invoker,
        ):
            process_game_finished(_learning_payload(
                domain_class=domain_class,
                run_id=run_id,
            ))
        kwargs = _last_memory_call(invoker)
        tags = kwargs.get("metadata", {}).get("tags", [])
        # Order is fixed: [domain, "scan-learnings", "{domain}-learnings", run_id].
        assert tags[0] == domain_class
        assert tags[1] == "scan-learnings"
        assert tags[2] == f"{domain_class}-learnings"
        assert tags[3] == run_id
