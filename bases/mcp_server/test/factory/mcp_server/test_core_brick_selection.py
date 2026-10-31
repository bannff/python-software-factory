"""Property tests for mcp_server core brick selection and logging."""

from __future__ import annotations

import logging
from unittest.mock import patch

import hypothesis.strategies as st
from hypothesis import given, settings

from factory.mcp_server.core import DEFAULT_EXCLUDE, _resolve_brick_names

_brick_name = st.text(
    min_size=1, max_size=20,
    alphabet=st.characters(whitelist_categories=("L", "N", "Pc")),
)
_brick_list = st.lists(_brick_name, min_size=0, max_size=15)
_SETTINGS = settings(max_examples=50)


def _mock_resolve(available: list[str], include: str = "", exclude: str = ""):
    """Run _resolve_brick_names with mocked BrickDiscovery."""
    config = {"include_bricks": include, "exclude_bricks": exclude}
    with patch(
        "factory.mcp_server.runtime.brick_selection.BrickDiscovery"
    ) as MockDisc:
        MockDisc.return_value.get_brick_names.return_value = available
        return _resolve_brick_names(config)


# ── _resolve_brick_names: include mode ──────────────────────────────

@given(
    available=_brick_list,
    include=st.lists(_brick_name, min_size=1, max_size=15),
)
@_SETTINGS
def test_include_mode_result_subset_of_both(available, include):
    result = _mock_resolve(available, include=",".join(include))
    result_set = set(result)
    assert result_set <= set(available)
    assert result_set <= set(include)


@given(
    available=st.lists(_brick_name, min_size=0, max_size=15, unique=True),
    include=st.lists(_brick_name, min_size=1, max_size=15),
)
@_SETTINGS
def test_include_mode_preserves_available_order(available, include):
    result = _mock_resolve(available, include=",".join(include))
    indices = [available.index(b) for b in result]
    assert indices == sorted(indices)


# ── _resolve_brick_names: exclude mode ──────────────────────────────

@given(available=_brick_list)
@_SETTINGS
def test_exclude_mode_never_contains_default_exclude(available):
    result = _mock_resolve(available)
    assert set(result) & DEFAULT_EXCLUDE == set()


@given(available=_brick_list)
@_SETTINGS
def test_exclude_mode_contains_all_non_excluded(available):
    result_set = set(_mock_resolve(available))
    for b in available:
        if b not in DEFAULT_EXCLUDE:
            assert b in result_set


@given(include=_brick_list)
@_SETTINGS
def test_empty_available_always_empty(include):
    assert _mock_resolve([], include=",".join(include)) == []


@given(available=_brick_list)
@_SETTINGS
def test_empty_include_falls_through_to_exclude(available):
    result = _mock_resolve(available, include="")
    assert set(result) & DEFAULT_EXCLUDE == set()


# ── Logging properties ─────────────────────────────────────────────

def test_include_mode_logs_dropped(caplog):
    with caplog.at_level(logging.WARNING, logger="factory.mcp_server.core"):
        _mock_resolve(["cache", "auth", "kb"], include="cache")
    warns = [r for r in caplog.records if r.levelno == logging.WARNING]
    msgs = [r.getMessage() for r in warns]
    assert any("excludes available" in m for m in msgs)
    full = " ".join(msgs)
    assert "auth" in full and "kb" in full


def test_include_mode_logs_stale(caplog):
    with caplog.at_level(logging.WARNING, logger="factory.mcp_server.core"):
        _mock_resolve(["cache"], include="cache,ghost")
    warns = [r.getMessage() for r in caplog.records if r.levelno == logging.WARNING]
    assert any("unknown" in m for m in warns)
    assert any("ghost" in m for m in warns)


def test_resolve_always_logs_info_count(caplog):
    with caplog.at_level(logging.INFO, logger="factory.mcp_server.core"):
        _mock_resolve(["cache", "auth"])
    info_msgs = [r.getMessage() for r in caplog.records if r.levelno == logging.INFO]
    assert any("Resolved" in m for m in info_msgs)


def test_include_no_warning_when_perfect_match(caplog):
    with caplog.at_level(logging.WARNING, logger="factory.mcp_server.core"):
        _mock_resolve(["cache", "auth"], include="cache,auth")
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert len(warnings) == 0
