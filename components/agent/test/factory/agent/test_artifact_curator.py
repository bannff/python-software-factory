from factory.agent.registry.defaults_artifacts import (
    ARTIFACT_CHAT_TOOLS, ARTIFACT_CURATOR_AGENT,
)


def test_artifact_curator_has_exact_public_tool_scope() -> None:
    assert ARTIFACT_CURATOR_AGENT.exact_tools is True
    assert ARTIFACT_CURATOR_AGENT.tools == ARTIFACT_CHAT_TOOLS
    assert len(ARTIFACT_CHAT_TOOLS) == len(set(ARTIFACT_CHAT_TOOLS))
    assert "artifacts_save" in ARTIFACT_CHAT_TOOLS
    assert "artifacts_revert" in ARTIFACT_CHAT_TOOLS
    assert "artifacts_mark_comment_review" in ARTIFACT_CHAT_TOOLS
    assert not {"artifacts_resolve_comment", "artifacts_delete_comment",
                "artifacts_purge"}.intersection(ARTIFACT_CHAT_TOOLS)


def test_artifact_curator_is_in_builtin_registry() -> None:
    from factory.agent.registry.defaults import get_default_agents
    by_id = {agent.id: agent for agent in get_default_agents()}
    assert by_id["artifact-curator"] is ARTIFACT_CURATOR_AGENT
