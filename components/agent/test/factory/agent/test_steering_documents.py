"""Agent steering document persistence, MCP, and injection contracts."""
from __future__ import annotations

from tempfile import TemporaryDirectory

from hypothesis import given, settings, strategies as st
from pydantic import ValidationError
import pytest

from factory.agent.mcp.contracts.steering import SteeringCreateInput, SteeringRefInput


@pytest.mark.asyncio
async def test_steering_create_list_read_update_and_stale_cas(tmp_path, monkeypatch) -> None:
    from factory.agent.server import create_tool_catalog

    monkeypatch.setenv("FACTORY_AGENT_STEERING_DIR", str(tmp_path))
    monkeypatch.setenv("SUPER_AGENT_ENABLE_AUTHORING_TOOLS", "1")
    catalog = create_tool_catalog()
    assert {"agent_list_steering", "agent_read_steering", "agent_create_steering",
            "agent_update_steering", "agent_delete_steering"} <= set(catalog.tool_map())
    created = await catalog.call_tool("agent_create_steering", {
        "document_id": "quality", "content": "# Quality\nRun focused tests.",
    })
    first = created.structured_content["data"]["document"]
    assert first["title"] == "Quality"
    listed = await catalog.call_tool("agent_list_steering", {})
    assert listed.structured_content["data"]["count"] == 1
    read = await catalog.call_tool("agent_read_steering", {"document_id": "quality"})
    assert "Run focused tests" in read.structured_content["data"]["content"]
    updated = await catalog.call_tool("agent_update_steering", {
        "document_id": "quality", "content": "# Quality\nRun all relevant tests.",
        "expected_sha256": first["sha256"],
    })
    second = updated.structured_content["data"]["document"]
    assert second["sha256"] != first["sha256"]
    stale = await catalog.call_tool("agent_update_steering", {
        "document_id": "quality", "content": "stale",
        "expected_sha256": first["sha256"],
    })
    assert stale.structured_content["error"] == "steering_revision_conflict"
    stale_delete = await catalog.call_tool("agent_delete_steering", {
        "document_id": "quality", "expected_sha256": first["sha256"],
    })
    assert stale_delete.structured_content["error"] == "steering_revision_conflict"
    missing_delete = await catalog.call_tool("agent_delete_steering", {
        "document_id": "nonexistent", "expected_sha256": second["sha256"],
    })
    assert missing_delete.structured_content["error"] == "steering_not_found"
    deleted = await catalog.call_tool("agent_delete_steering", {
        "document_id": "quality", "expected_sha256": second["sha256"],
    })
    assert deleted.structured_content["data"] == {"deleted": True, "document_id": "quality"}
    after_delete = await catalog.call_tool("agent_list_steering", {})
    assert after_delete.structured_content["data"]["count"] == 0


def test_steering_inputs_reject_traversal_extra_and_nul() -> None:
    for value in ("../escape", "Upper", "has_underscore", "a" * 65):
        with pytest.raises(ValidationError):
            SteeringRefInput(document_id=value)
    with pytest.raises(ValidationError):
        SteeringRefInput.model_validate({"document_id": "safe", "extra": True})
    with pytest.raises(ValidationError):
        SteeringCreateInput(document_id="safe", content="bad\x00content")


@settings(max_examples=15, deadline=None)
@given(
    first=st.text(min_size=1, max_size=60).filter(lambda text: "\x00" not in text and bool(text.strip())),
    second=st.text(min_size=1, max_size=60).filter(lambda text: "\x00" not in text and bool(text.strip())),
)
def test_steering_updates_change_injected_digest(first: str, second: str) -> None:
    import os

    from factory.agent.runtime import steering_documents as docs

    previous = os.environ.get("FACTORY_AGENT_STEERING_DIR")
    with TemporaryDirectory() as temporary:
        os.environ["FACTORY_AGENT_STEERING_DIR"] = temporary
        try:
            created = docs.create_steering("generated", first)
            prompt1, digest1 = docs.steering_prompt()
            updated = docs.update_steering("generated", second, created.sha256)
            prompt2, digest2 = docs.steering_prompt()
            assert first.strip() in prompt1 and second.strip() in prompt2
            if first.strip() != second.strip():
                assert updated.sha256 != created.sha256
                assert digest2 != digest1
        finally:
            if previous is None:
                os.environ.pop("FACTORY_AGENT_STEERING_DIR", None)
            else:
                os.environ["FACTORY_AGENT_STEERING_DIR"] = previous
