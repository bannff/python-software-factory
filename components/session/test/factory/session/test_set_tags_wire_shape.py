"""``session_set_tags`` must accept the JSON shape the UI sends (a list) (#51)."""
from __future__ import annotations

from pathlib import Path

from .test_lifecycle_tools import _create, _env, _tools


def test_set_tags_accepts_a_json_list_and_round_trips(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_set_tags"].fn(
        session_id=session.session_id, tags=["probe-tag"],
        expected_revision=session.revision, envelope=_env(),
    )
    assert result.ok is True, result.error
    assert result.data.session.tags == ("probe-tag",)


def test_set_pinned_messages_accepts_a_json_list(tmp_path: Path) -> None:
    tools = _tools(tmp_path)
    session = _create(tools)
    result = tools["session_set_pinned_messages"].fn(
        session_id=session.session_id, pinned_message_ids=["m1", "m2"],
        expected_revision=session.revision, envelope=_env(),
    )
    assert result.ok is True, result.error
    assert result.data.session.pinned_message_ids == ("m1", "m2")


def test_a_non_array_still_fails_strict_validation(tmp_path: Path) -> None:
    import pytest
    from factory.mcp_utils.interface import SchemaMigrationError

    tools = _tools(tmp_path)
    session = _create(tools)
    with pytest.raises(SchemaMigrationError):
        tools["session_set_tags"].fn(
            session_id=session.session_id, tags="probe-tag",
            expected_revision=session.revision, envelope=_env(),
        )
