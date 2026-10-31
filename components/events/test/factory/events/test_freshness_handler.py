"""Tests for eval-freshness staleness handler (bd:python-factory-v7imt.4).

Behavior contracts:
1. A completion event on a STALE experiment triggers a persisted eval (source="freshness")
2. A completion on a FRESH experiment does NOT persist
3. An eval.freshness.due event routes to the same handler
4. A persist failure is defensive (does not break the completion/timer path)
5. Staleness threshold is configurable via env var
"""

from __future__ import annotations

import os
import time
from unittest.mock import MagicMock, patch

import pytest

from factory.events.runtime.freshness_handler import (
    _DEFAULT_STALENESS_THRESHOLD_S,
    _get_staleness_threshold,
    _is_stale,
    handle_freshness_check,
)
from pydantic import BaseModel
from factory.mcp_utils.runtime.tool_result import ToolResult


class _LatestScore(BaseModel):
    timestamp: float | None = None


from factory.events.runtime.models import Event


def _make_event(event_type: str = "graph.completed", **payload_overrides) -> Event:
    payload = {
        "run_id": "run-123",
        "workflow_id": "wf-abc",
        "target_app": "my-experiment",
        "workflow_type": "security-scan",
        "vuln_class": "idor",
        "domain_class": "idor",
        **payload_overrides,
    }
    return Event(type=event_type, source="test", payload=payload)


class TestStalenessThreshold:
    """Contract: staleness threshold is configurable."""

    def test_default_threshold(self):
        with patch.dict(os.environ, {}, clear=True):
            # Remove the env var if present
            os.environ.pop("FRESHNESS_STALENESS_THRESHOLD_S", None)
            assert _get_staleness_threshold() == float(_DEFAULT_STALENESS_THRESHOLD_S)

    def test_env_override(self):
        with patch.dict(os.environ, {"FRESHNESS_STALENESS_THRESHOLD_S": "7200"}):
            assert _get_staleness_threshold() == 7200.0

    def test_env_invalid_falls_back(self):
        with patch.dict(os.environ, {"FRESHNESS_STALENESS_THRESHOLD_S": "not-a-number"}):
            assert _get_staleness_threshold() == float(_DEFAULT_STALENESS_THRESHOLD_S)

    def test_env_zero_falls_back(self):
        with patch.dict(os.environ, {"FRESHNESS_STALENESS_THRESHOLD_S": "0"}):
            assert _get_staleness_threshold() == float(_DEFAULT_STALENESS_THRESHOLD_S)


class TestIsStale:
    """Contract: staleness logic."""

    def test_none_timestamp_is_stale(self):
        assert _is_stale(None, 3600) is True

    def test_old_timestamp_is_stale(self):
        old_ts = time.time() - 7200  # 2 hours ago
        assert _is_stale(old_ts, 3600) is True

    def test_recent_timestamp_is_fresh(self):
        recent_ts = time.time() - 60  # 1 minute ago
        assert _is_stale(recent_ts, 3600) is False


class TestHandleFreshnessCheckStale:
    """Contract: stale experiment triggers eval persist."""

    def test_stale_triggers_persist(self):
        invoker = MagicMock()
        # evals_get_latest_score returns None → never evaluated → stale
        invoker.return_value = ToolResult(data=_LatestScore(timestamp=None))
        invoker.side_effect = lambda tool, **kwargs: (
            ToolResult(data=_LatestScore(timestamp=None)) if tool == "evals_get_latest_score"
            else None
        )

        event = _make_event("graph.completed")
        result = handle_freshness_check(event, invoker)

        assert result["action"] == "triggered"
        # Verify evals_persist_score was called with source="freshness"
        persist_calls = [
            c for c in invoker.call_args_list
            if c[0][0] == "evals_persist_score"
        ]
        assert len(persist_calls) == 1
        call_kwargs = persist_calls[0][1]
        assert call_kwargs["source"] == "freshness"
        assert call_kwargs["target_app"] == "my-experiment"

    def test_never_evaluated_is_stale(self):
        invoker = MagicMock()
        # evals_get_latest_score raises (no data) → None → stale
        invoker.side_effect = lambda tool, **kwargs: (
            ToolResult(ok=False, data=None, error="unavailable") if tool == "evals_get_latest_score" else None
        )

        event = _make_event("swarm.completed")
        result = handle_freshness_check(event, invoker)

        assert result["action"] == "triggered"


class TestHandleFreshnessCheckFresh:
    """Contract: fresh experiment does NOT persist."""

    def test_fresh_skips_persist(self):
        recent_ts = time.time() - 60  # 1 minute ago → well within threshold

        invoker = MagicMock()
        invoker.side_effect = lambda tool, **kwargs: (
            ToolResult(data=_LatestScore(timestamp=recent_ts)) if tool == "evals_get_latest_score"
            else None
        )

        event = _make_event("graph.completed")
        result = handle_freshness_check(event, invoker)

        assert result["action"] == "skipped_fresh"
        # Ensure persist was NOT called
        persist_calls = [
            c for c in invoker.call_args_list
            if c[0][0] == "evals_persist_score"
        ]
        assert len(persist_calls) == 0


class TestCadenceEventRoutes:
    """Contract: eval.freshness.due routes to the same handler."""

    def test_cadence_event_triggers_check(self):
        invoker = MagicMock()
        # Stale → triggers
        invoker.side_effect = lambda tool, **kwargs: (
            ToolResult(data=_LatestScore(timestamp=None)) if tool == "evals_get_latest_score"
            else None
        )

        event = _make_event("eval.freshness.due")
        result = handle_freshness_check(event, invoker)

        assert result["action"] == "triggered"
        persist_calls = [
            c for c in invoker.call_args_list
            if c[0][0] == "evals_persist_score"
        ]
        assert len(persist_calls) == 1


class TestPersistFailureDefensive:
    """Contract: persist failure never breaks the caller."""

    def test_persist_error_returns_triggered_not_exception(self):
        call_count = {"get": 0, "persist": 0}

        def _invoker(tool, **kwargs):
            if tool == "evals_get_latest_score":
                call_count["get"] += 1
                return ToolResult(data=_LatestScore(timestamp=None))  # stale
            if tool == "evals_persist_score":
                call_count["persist"] += 1
                raise RuntimeError("DB connection refused")
            return None

        event = _make_event("graph.completed")
        # Must NOT raise
        result = handle_freshness_check(event, _invoker)

        # Handler completes — action is still "triggered" even though persist failed
        assert result["action"] == "triggered"
        assert call_count["persist"] == 1

    def test_get_latest_error_still_triggers(self):
        """If we can't determine freshness, assume stale (safe default)."""
        def _invoker(tool, **kwargs):
            if tool == "evals_get_latest_score":
                raise ConnectionError("timeout")
            return None

        event = _make_event("graph.completed")
        result = handle_freshness_check(event, _invoker)

        # _get_last_eval_timestamp returns None on error → _is_stale(None) → True
        assert result["action"] == "triggered"


class TestSubscriptionYAMLLoading:
    """Verify subscription YAMLs are valid and loadable."""

    _SUBS_DIR = os.path.join(
        os.path.dirname(os.path.abspath(__file__)),
        "..", "..", "..", "src", "factory", "events", "subscriptions",
    )

    def test_completion_subscription_loads(self):
        import yaml
        from factory.events.runtime.subscriptions import SubscriptionDefinition

        yaml_path = os.path.join(self._SUBS_DIR, "auto-freshness-on-completion.yaml")
        data = yaml.safe_load(open(yaml_path).read())
        sub = SubscriptionDefinition.model_validate(data)
        assert sub.id == "auto-freshness-on-graph-complete"
        assert sub.event_type == "graph.completed"
        assert sub.handler == "mcp:freshness_dispatch"
        assert sub.enabled is True

    def test_cadence_subscription_loads(self):
        import yaml
        from factory.events.runtime.subscriptions import SubscriptionDefinition

        yaml_path = os.path.join(self._SUBS_DIR, "auto-freshness-on-cadence.yaml")
        data = yaml.safe_load(open(yaml_path).read())
        sub = SubscriptionDefinition.model_validate(data)
        assert sub.id == "auto-freshness-on-cadence"
        assert sub.event_type == "eval.freshness.due"
        assert sub.handler == "mcp:freshness_dispatch"
        assert sub.enabled is True

    def test_swarm_subscription_loads(self):
        import yaml
        from factory.events.runtime.subscriptions import SubscriptionDefinition

        yaml_path = os.path.join(self._SUBS_DIR, "auto-freshness-on-swarm-complete.yaml")
        data = yaml.safe_load(open(yaml_path).read())
        sub = SubscriptionDefinition.model_validate(data)
        assert sub.id == "auto-freshness-on-swarm-complete"
        assert sub.event_type == "swarm.completed"
        assert sub.handler == "mcp:freshness_dispatch"
