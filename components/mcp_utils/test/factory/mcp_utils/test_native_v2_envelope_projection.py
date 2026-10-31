"""Trusted native envelope projection into strict brick-local DTOs."""
from pydantic import BaseModel, ConfigDict, Field

from factory.mcp_utils.interface import project_envelope_arguments


class DTO(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Envelope(DTO):
    tenant_id: str | None = None
    principal_id: str | None = None
    session_id: str | None = None
    request_id: str | None = None
    agent_id: str | None = None
    attributes: dict = Field(default_factory=dict)


class Input(DTO):
    value: str
    envelope: Envelope | None = None


def handler() -> None:
    pass


handler._mcp_input_model = Input


def test_trusted_envelope_projects_declared_fields_and_fences_authority() -> None:
    result = project_envelope_arguments(handler, {
        "value": "ok",
        "envelope": {
            "tenant_id": "forged-tenant", "principal_id": "forged-owner",
            "agent_id": "forged-agent", "session_id": "internal-session",
            "request_id": "internal-request", "attributes": {"forged": True},
        },
    }, {
        "tenant_id": "trusted-tenant", "principal_id": "trusted-owner",
        "session_id": None, "request_id": None, "agent_id": None,
        "attributes": {"trusted": True}, "workflow_id": "drop-me",
    })

    assert result["envelope"] == {
        "tenant_id": "trusted-tenant", "principal_id": "trusted-owner",
        "session_id": "internal-session", "request_id": "internal-request",
        "attributes": {"trusted": True},
    }
    Input.model_validate(result)
