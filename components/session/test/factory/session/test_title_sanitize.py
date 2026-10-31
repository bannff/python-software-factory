"""Unit tests for the title sanitizer (``_sanitize``, row 17)."""
from __future__ import annotations

from factory.session.runtime.title_generation import _sanitize


def test_sanitize_strips_wrapping_quotes_and_whitespace() -> None:
    assert _sanitize('  "Deploy pipeline fix"  ') == "Deploy pipeline fix"


def test_sanitize_collapses_internal_whitespace_runs() -> None:
    assert _sanitize("Deploy   pipeline\n\nfix") == "Deploy pipeline fix"


def test_sanitize_truncates_at_max_length() -> None:
    long_text = "x" * 200
    result = _sanitize(long_text)
    assert len(result) <= 80


def test_sanitize_falls_back_to_untitled_for_empty_result() -> None:
    assert _sanitize("   ") == "Untitled chat"
    assert _sanitize('""') == "Untitled chat"
