"""Tests for emit.py — cross-brick event emission helper.

Covers: tool_invoker registered, tool_invoker None, tool_invoker raises,
user_id inclusion/exclusion in payload.
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

from factory.memory.runtime.emit import emit_memory_event


class TestEmitMemoryEvent:
    def test_calls_invoker_when_registered(self):
        invoker = MagicMock()
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            emit_memory_event("memory.store", {"memory_id": "m1"}, user_id="u1")
        invoker.assert_called_once_with(
            "events_publish",
            source="memory",
            event_type="memory.store",
            payload={"memory_id": "m1", "user_id": "u1"},
            run_id_authoritative=False,
        )

    def test_silently_returns_when_invoker_none(self):
        with patch("factory.mcp_utils.registry._services", {}):
            # Should not raise
            emit_memory_event("memory.store", {"memory_id": "m1"})

    def test_silently_catches_invoker_exception(self):
        invoker = MagicMock(side_effect=RuntimeError("boom"))
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            # Should not raise
            emit_memory_event("memory.store", {"memory_id": "m1"})

    def test_user_id_included_in_payload(self):
        invoker = MagicMock()
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            emit_memory_event("memory.store", {"k": "v"}, user_id="u42")
        payload = invoker.call_args[1]["payload"]
        assert payload["user_id"] == "u42"

    def test_user_id_none_excluded_from_payload(self):
        invoker = MagicMock()
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            emit_memory_event("memory.store", {"k": "v"}, user_id=None)
        payload = invoker.call_args[1]["payload"]
        assert "user_id" not in payload

    def test_payload_not_mutated(self):
        invoker = MagicMock()
        with patch("factory.mcp_utils.registry._services", {"tool_invoker": invoker}):
            original = {"memory_id": "m1"}
            emit_memory_event("memory.store", original, user_id="u1")
        assert "user_id" not in original

    def test_import_error_silently_caught(self):
        with patch("factory.memory.runtime.emit.logger"):
            with patch.dict("sys.modules", {"factory.mcp_utils.interface": None}):
                # Force re-import to trigger ImportError path
                import importlib
                import factory.memory.runtime.emit as mod
                importlib.reload(mod)
                # After reload with broken import, calling should not raise
                mod.emit_memory_event("memory.store", {"memory_id": "m1"})
            # Restore module
            import importlib
            import factory.memory.runtime.emit as mod
            importlib.reload(mod)
